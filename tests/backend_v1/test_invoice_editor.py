"""Provider output is mocked here; real PostgreSQL, auth, money, ledger and PDF checks."""
from datetime import date
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from operations.integrations.invoice_gemini import InvoiceGemini
from operations.persistence.database import sessions
from operations.persistence.models import Benefit, Invoice, Movement
from operations.domain import service_memberships
from operations.domain.common import Actor, Problem


def test_portable_gemini_schema_preserves_title_and_nullable_prices():
    from operations.integrations.invoice_gemini import response_schema
    schema = response_schema()
    assert schema["properties"]["title"] == {"type": "string"}
    assert schema["properties"]["lines"]["items"]["properties"]["unit_price"] == {"type": ["string", "null"]}
    assert "$defs" not in schema


@pytest.fixture
def records(api):
    customer = api.create("customers", "Invoice customer", {"email":"billing@example.com"})
    site = api.create("properties", "Home", {"address":"12 Main St"}, parent_id=customer["id"])
    unit = api.create("equipment", "Sink", {"trade":"Plumbing"}, parent_id=site["id"])
    return {"customer_id":customer["id"],"property_id":site["id"],"equipment_id":unit["id"],"job_id":None,
        "trade":"Plumbing","service":"repair","service_date":date.today().isoformat()}


def line(description="Sink repair", price="150", category="unclassified", source="Sink is broken, needs repair 150$"):
    return {"description":description,"quantity":"1","unit_price":price,"category":category,"source_text":source,"pricebook_id":None,"apply_membership":False}


def draft(records, lines=None):
    return {**records,"source_text":"Sink is broken, needs repair 150$","generation_source_text":"Sink is broken, needs repair 150$",
        "title":"Sink repair","description":"Requested sink repair","lines":lines or [line()],"missing_information":[],"ambiguities":[],
        "invoice_date":date.today().isoformat(),"due_date":date.today().isoformat(),"review_note":"Reviewed explicit requested charge.","review_confirmed":True}


@pytest.fixture
def configured(monkeypatch):
    for key,value in {"GOOB_INVOICE_TAX_BPS":"0","GOOB_INVOICE_COMPANY_NAME":"Goob Plumbing","GOOB_INVOICE_COMPANY_ADDRESS":"1 Company Street","GOOB_INVOICE_COMPANY_CONTACT":"billing@goob.test"}.items():
        monkeypatch.setenv(key,value)


@pytest.mark.parametrize("source,lines,total",[
    ("Sink is broken, needs repair 150$",[line()],15000),
    ("Labor $150, replacement valve $25",[line("Labor","150","labor","Labor $150"),line("Replacement valve","25","material","replacement valve $25")],17500)])
def test_mocked_generation_examples(api, records, monkeypatch, source, lines, total):
    def generate(self,text,context):
        assert text==source and set(context)=={"trade","service","currency"}
        return {"title":"Service charges","description":"Requested work","lines":lines,"missing_information":[],"ambiguities":[]},{"provider":"mock"}
    monkeypatch.setattr(InvoiceGemini,"generate",generate)
    response=api.request("POST","/invoices/generate",{**records,"source_text":source})
    assert len(response["extraction"]["lines"])==len(lines)
    preview=api.request("POST","/invoices/preview",draft(records,response["extraction"]["lines"]))
    assert preview["subtotal_cents"]==total
    assert "completed" not in response["extraction"]["description"].lower()


def test_missing_and_fabricated_prices_require_review(api, records, monkeypatch, configured):
    monkeypatch.setattr(InvoiceGemini,"generate",lambda *args:({"title":"Sink repair","description":"Requested repair","lines":[line(price="350",source="Sink needs repair")],"missing_information":[],"ambiguities":[]},{}))
    generated=api.request("POST","/invoices/generate",{**records,"source_text":"Sink needs repair"})
    assert generated["extraction"]["lines"][0]["unit_price"] is None
    d=draft(records,generated["extraction"]["lines"])
    preview=api.request("POST","/invoices/preview",d)
    assert preview["partial"] and not preview["can_finalize"]
    response=api.request("POST","/invoices/save",{"id":str(uuid4()),"draft":d,"finalize":True,"preview_token":preview["preview_token"]},expected=422)
    assert "price required" in response["error"]


def test_save_reopen_finalize_pdf_export_and_idempotence(api, records, configured, engine):
    d=draft(records);identifier=str(uuid4());key=str(uuid4())
    payload={"id":identifier,"draft":d}
    saved=api.request("POST","/invoices/save",payload,key=key)
    assert api.request("POST","/invoices/save",payload,key=key)==saved
    api.request("POST","/invoices/save",payload,expected=409)
    assert saved["number"].startswith("INV-") and saved["status"]=="draft"
    assert api.request("GET","/invoices/"+identifier)["snapshot"]["draft"]==d
    assert api.request("GET","/invoices?q=Invoice%20customer")[0]["id"]==identifier
    assert api.request("GET","/invoices?customer_id="+records["customer_id"])[0]["id"]==identifier
    d["lines"][0]["quantity"]="2";d["lines"][0]["unit_price"]="100.25"
    preview=api.request("POST","/invoices/preview",d)
    assert preview["total_cents"]==20050
    final_payload={"id":identifier,"expected_revision":1,"draft":d,"finalize":True,"preview_token":preview["preview_token"]}
    finalized=api.request("POST","/invoices/save",final_payload,key="finalize")
    assert api.request("POST","/invoices/save",final_payload,key="finalize")==finalized
    assert finalized["status"]=="finalized" and len(finalized["snapshot"]["review_changes"])==2
    pdf=api.client.get("/api/v1/invoices/"+identifier+"/pdf",headers=api.headers())
    assert pdf.status_code==200 and pdf.content.startswith(b"%PDF")
    import fitz
    text="".join(p.get_text() for p in fitz.open(stream=pdf.content,filetype="pdf"))
    assert "Sink repair" in text and "$200.50" in text and "FINALIZED" in text
    export=api.request("GET","/invoices/"+identifier+"/accounting-export")
    assert export["state"]=="finalized" and export["sync_status"]=="not_posted"
    api.request("POST","/invoices/save",{**final_payload,"expected_revision":2},expected=409)
    with sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(Invoice).where(Invoice.tenant_id==api.tenant))==1
        assert db.scalar(select(func.count()).select_from(Movement).where(Movement.tenant_id==api.tenant))==0
        assert db.scalar(select(func.count()).select_from(Benefit).where(Benefit.tenant_id==api.tenant))==0


def test_membership_only_eligible_labor_and_no_allowance_consumption(api,records,engine,configured):
    actor=Actor(api.tenant,"owner","owner",("a","b"))
    with sessions(engine)() as db:
        service_memberships.run(db,actor,{"operation":"plan","values":{"name":"Care","trades":["Plumbing"],"termDays":365,"visits":2,"discountRules":[{"kind":"labor","service":"repair","percent":15}]}})
        plan=service_memberships.snapshot(db,actor,[])[0][0]
        service_memberships.run(db,actor,{"operation":"enroll","values":{"planId":plan["id"],"equipmentId":records["equipment_id"],"customerId":records["customer_id"],"propertyId":records["property_id"],"starts":date.today().isoformat()}})
        db.commit()
    lines=[line("Labor","150","labor","Labor $150"),line("Valve","25","material","valve $25"),line("Repair","100","unclassified","repair $100")]
    d=draft(records,lines)
    proposed=api.request("POST","/invoices/preview",d)
    assert [l["proposed_discount_cents"] for l in proposed["lines"]]==[2250,0,0]
    assert proposed["total_cents"]==27500
    d["lines"][0]["apply_membership"]=True
    applied=api.request("POST","/invoices/preview",d)
    assert applied["total_cents"]==25250
    api.request("POST","/invoices/save",{"id":str(uuid4()),"draft":d,"finalize":True,"preview_token":applied["preview_token"]})
    with sessions(engine)() as db:
        assert db.scalar(select(func.sum(Benefit.amount)).where(Benefit.tenant_id==api.tenant))==2
        assert db.scalar(select(func.count()).select_from(Movement).where(Movement.tenant_id==api.tenant))==0
    rental=api.create("properties","Rental",{"address":"99 Other Street"},parent_id=records["customer_id"])
    unit=api.create("equipment","Rental sink",{"trade":"Plumbing"},parent_id=rental["id"])
    d.update(property_id=rental["id"],equipment_id=unit["id"])
    wrong=api.request("POST","/invoices/preview",d)
    assert wrong["discount_cents"]==0 and not wrong["can_finalize"]


def test_missing_configuration_access_and_changed_preview(api, records, monkeypatch, configured):
    d=draft(records)
    preview=api.request("POST","/invoices/preview",d)
    monkeypatch.setenv("GOOB_INVOICE_TAX_BPS","725")
    api.request("POST","/invoices/save",{"id":str(uuid4()),"draft":d,"finalize":True,"preview_token":preview["preview_token"]},expected=409)
    monkeypatch.delenv("GOOB_INVOICE_TAX_BPS")
    assert not api.request("POST","/invoices/preview",d)["can_finalize"]
    api.request("POST","/invoices/save",{"id":str(uuid4()),"draft":d},role="viewer",expected=403)
    api.request("POST","/invoices/generate",{**records,"customer_id":"unknown","source_text":"Sink $150"},expected=404)
    api.request("POST","/invoices/preview",d,company=api.other,expected=403)


def test_gemini_missing_configuration_and_failures(api,records,monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY",raising=False)
    api.request("POST","/invoices/generate",{**records,"source_text":"Sink $150"},expected=503)
    for status in (429,504,502):
        def fail(*args):raise Problem("Provider unavailable; enter manually.",status)
        monkeypatch.setattr(InvoiceGemini,"generate",fail)
        api.request("POST","/invoices/generate",{**records,"source_text":"Sink $150"},expected=status)
    monkeypatch.setattr(InvoiceGemini,"generate",lambda *args:({"total":999},{}))
    api.request("POST","/invoices/generate",{**records,"source_text":"Sink $150"},expected=502)
    assert api.request("POST","/invoices/save",{"id":str(uuid4()),"draft":draft(records)})["status"]=="draft"


def test_confirmed_pricebook_fractional_rounding_and_tax(api,records,configured,monkeypatch):
    sku=api.create("skus","Valve",{"price_cents":10025,"cost_cents":9000,"barcode":"TEST-VALVE"})
    l=line("Valve",None,"material","replacement valve");l.update(quantity="0.5",pricebook_id=sku["id"])
    monkeypatch.setenv("GOOB_INVOICE_TAX_BPS","725")
    preview=api.request("POST","/invoices/preview",draft(records,[l]))
    assert preview["lines"][0]["unit_price"]=="100.25"
    assert preview["subtotal_cents"]==5013 and preview["tax_cents"]==363 and preview["total_cents"]==5376
    other=api.create("skus","Other branch",{"price_cents":100,"cost_cents":50,"barcode":"OTHER"},branch="b")
    l["pricebook_id"]=other["id"]
    api.request("POST","/invoices/preview",draft(records,[l]),expected=422)


def test_explicit_credit_generation_preview_persistence_and_bounds(api, records, configured, monkeypatch):
    source = "Sink repair 150$ credit 20$"
    lines = [line(source="Sink repair 150$"), line("Credit", "-20", "credit", "credit 20$")]
    monkeypatch.setattr(InvoiceGemini,"generate",lambda *args:({"title":"Sink repair","description":"Requested repair and credit","lines":lines,"missing_information":[],"ambiguities":[]},{}))
    generated=api.request("POST","/invoices/generate",{**records,"source_text":source})["extraction"]
    assert generated["lines"][1]["unit_price"]=="-20"
    d=draft(records,generated["lines"])
    preview=api.request("POST","/invoices/preview",d)
    assert preview["total_cents"]==13000 and preview["lines"][1]["total_cents"]==-2000
    assert preview["lines"][1]["discount_cents"]==0
    saved=api.request("POST","/invoices/save",{"id":str(uuid4()),"draft":d})
    assert api.request("GET","/invoices/"+saved["id"])["snapshot"]["lines"][1]["total_cents"]==-2000
    d["lines"][1]["category"]="other"
    api.request("POST","/invoices/preview",d,expected=422)
    d["lines"][1].update(category="credit",unit_price="-200")
    assert not api.request("POST","/invoices/preview",d)["can_finalize"]

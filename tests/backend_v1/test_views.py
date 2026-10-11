from operations.domain.views import defaults
import pytest
from pydantic import ValidationError
from operations.api_v1.schemas import SKU

@pytest.mark.parametrize("url",["http://example.com/a.png","https://127.0.0.1/a.png","https://localhost./a.png","https://user:secret@example.com/a.png","/inventory-images/../a.png","data:image/png;base64,abc"])
def test_unsafe_image_urls_rejected(url):
    with pytest.raises(ValidationError):SKU(image_url=url)

def test_personal_views_company_defaults_and_revision(api):
    original=api.request("GET","/views/inventory")
    assert not original["personal_override"]
    settings=defaults("inventory")
    settings["views"]["Night shift"]={**settings["views"]["Default"],"theme":"after-hours","presentation":"card","density":"compact","hidden":["ledger"]}
    settings["active"]="Night shift"
    api.request("POST","/views/inventory",{"settings":settings,"expected_revision":0},role="viewer")
    assert api.request("GET","/views/inventory",role="viewer")["settings"]==settings
    assert api.request("GET","/views/inventory")["settings"]==original["settings"]
    api.request("POST","/views/inventory",{"settings":settings,"expected_revision":0},role="viewer",expected=409)
    api.request("POST","/views/inventory",{"settings":settings,"company":True,"expected_revision":0},role="office",expected=403)
    company=defaults("inventory");company["views"]["Default"]["theme"]="workshop"
    api.request("POST","/views/inventory",{"settings":company,"company":True,"expected_revision":0})
    assert api.request("GET","/views/inventory",role="office")["settings"]==company
    assert api.request("GET","/views/inventory",role="viewer")["settings"]==settings
    inherited=api.request("POST","/views/inventory",{"inherit":True,"expected_revision":1},role="viewer")
    assert inherited["settings"]==company and not inherited["personal_override"]
    assert not api.request("GET","/views/jobs",role="viewer")["personal_override"]
    assert api.request("GET","/views/inventory",role="other",company=api.other)["settings"]==defaults("inventory")
    api.request("GET","/views/inventory",company=api.other,expected=403)

def test_dispatch_display_choices_restore(api):
    settings=defaults("dispatch")
    settings["views"]["Default"].update(dispatch_names=False,dispatch_routes=False,dispatch_status="Unassigned")
    api.request("POST","/views/dispatch",{"settings":settings,"expected_revision":0})
    assert api.request("GET","/views/dispatch")["settings"]==settings

def test_invalid_view_choices_cannot_hide_required_fields(api):
    settings=defaults("inventory")
    settings["views"]["Default"]["hidden"]=["stock"]
    api.request("POST","/views/inventory",{"settings":settings,"expected_revision":0},expected=422)
    settings["views"]["Default"]["hidden"]=[]
    settings["views"]["Default"]["columns"]=["image","image"]
    api.request("POST","/views/inventory",{"settings":settings,"expected_revision":0},expected=422)
    api.request("GET","/views/unknown",expected=404)

def test_image_changes_preserve_stock_and_permissions(api):
    sku=api.create("skus","Circuit breaker",{"barcode":"IMAGE-TEST"})
    location=api.create("locations","Warehouse",{"location_type":"warehouse"})
    api.request("POST","/inventory/commands",{"action":"receive","sku_id":sku["id"],"location_id":location["id"],"quantity":8,"reason":"Initial stock"})
    before=api.request("GET","/inventory/balances")
    values={"sku_id":sku["id"],"expected_revision":sku["revision"],"image_url":"https://example.com/breaker.webp","image_alt":"Circuit breaker"}
    rejected=api.client.post("/api/dispatch",json={"type":"image","values":values},headers=api.headers("viewer" )|{"Idempotency-Key":"viewer-image"})
    assert rejected.status_code==403
    assert api.request("GET","/inventory/balances")==before
    r=api.client.post("/api/dispatch",json={"type":"image","values":values},headers=api.headers()|{"Idempotency-Key":"owner-image"})
    assert r.status_code==200,r.text
    assert api.request("GET","/inventory/balances")==before
    assert api.request("GET","/records/skus/"+sku["id"])["data"]["image_alt"]=="Circuit breaker"

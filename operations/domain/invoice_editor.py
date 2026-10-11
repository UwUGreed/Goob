"""Independent invoices: exact cents, reviewed evidence, and no operational side effects."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import os
import re
from types import SimpleNamespace
from sqlalchemy import text
from operations.domain import agreements, service_memberships
from operations.domain.common import Problem, dump, event, get, module, record
from operations.persistence.models import Invoice


def selection(db, actor, p, action="read"):
    module(db, actor, "billing")
    customer = record(db, actor, p["customer_id"], "customers", action)
    site = record(db, actor, p["property_id"], "properties", action)
    if site.parent_id != customer.id or site.branch_id != customer.branch_id:
        raise Problem("Select a property belonging to this customer and branch.", 422)
    job = record(db, actor, p["job_id"], "jobs", action) if p.get("job_id") else None
    if job and (job.customer_id != customer.id or job.property_id != site.id or job.branch_id != site.branch_id):
        raise Problem("Linked job does not belong to the selected customer and property.", 422)
    equipment_id = p.get("equipment_id") or (job.equipment_id if job else None)
    unit = record(db, actor, equipment_id, "equipment", action) if equipment_id else None
    if job and unit and unit.id != job.equipment_id:
        raise Problem("Linked job and covered equipment must match.", 422)
    if unit and (unit.parent_id != site.id or unit.branch_id != site.branch_id or unit.data["trade"] != p["trade"]):
        raise Problem("Select matching equipment, property and trade.", 422)
    return customer, site, job, unit


def settings(db, actor):
    # The old accounting workflow intentionally has no tax configuration. Do not infer a rate.
    raw = os.environ.get("GOOB_INVOICE_TAX_BPS", "")
    tax = int(raw) if raw.isdigit() and 0 <= int(raw) <= 10000 else None
    return {"currency": "USD", "tax_bps": tax,
        "tax_reason": "Configured rate on net charges" if tax is not None else "Tax configuration missing; draft only",
        "company": {"name": os.environ.get("GOOB_INVOICE_COMPANY_NAME", ""),
            "address": os.environ.get("GOOB_INVOICE_COMPANY_ADDRESS", ""),
            "contact": os.environ.get("GOOB_INVOICE_COMPANY_CONTACT", "")}}


def cents(value):
    return int((Decimal(value) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def generated_evidence(extraction, source):
    """Reject fabricated lines; unsupported prices/quantities stay unresolved for review."""
    if any(len(x) > 500 for x in extraction["missing_information"] + extraction["ambiguities"]):
        raise Problem("Gemini returned invalid review information.", 502)
    claims = re.findall(r"\b(?:completed|performed|repaired|fixed|paid|installed|replaced)\b", extraction["title"]+" "+extraction["description"]+" "+" ".join(l["description"] for l in extraction["lines"]), re.I)
    if any(not re.search(r"\b"+re.escape(claim)+r"\b",source,re.I) for claim in claims):
        raise Problem("Gemini returned an unsupported work-completion claim. Use manual entry.", 502)
    seen = set()
    for line in extraction["lines"]:
        quote = line["source_text"]
        if not quote.strip() or quote not in source or quote in seen:
            raise Problem("Gemini returned unsupported or duplicated charge evidence. Use manual entry.", 502)
        seen.add(quote)
        amounts = re.findall(r"\$\s*(\d+(?:\.\d{1,2})?)|\b(\d+(?:\.\d{1,2})?)\s*\$", quote)
        explicit = [a or b for a,b in amounts]
        if line["category"] == "credit" and not re.search(r"\b(?:credit|refund)\b", quote, re.I):
            raise Problem("Gemini proposed a credit without explicit source evidence. Review manually.", 502)
        if line["unit_price"] is not None and not any(cents(a) == abs(cents(line["unit_price"])) for a in explicit):
            line["unit_price"] = None
            extraction["missing_information"].append("Confirm the price for " + line["description"])
        if line["unit_price"] is not None:
            if line["category"] == "credit":
                line["unit_price"] = format(-abs(Decimal(line["unit_price"])), "f")
            elif Decimal(line["unit_price"]) < 0:
                raise Problem("Negative charges require an explicitly supported credit. Review manually.", 502)
        if Decimal(line["quantity"]) != 1 and not re.search(r"\b"+re.escape(line["quantity"])+r"\s*(?:x|×|units?|hours?|each|valves?)\b", quote, re.I):
            line["quantity"] = "1"
            extraction["ambiguities"].append("Confirm quantity for " + line["description"])
        if line["category"] == "labor" and not re.search(r"\blabou?r\b", quote, re.I):
            line["category"] = "unclassified"
            extraction["ambiguities"].append("Confirm eligible charge category for " + line["description"])
        line["apply_membership"], line["pricebook_id"] = False, None
    return extraction


def preview(db, actor, p):
    customer, site, job, unit = selection(db, actor, p)
    config = settings(db, actor)
    issues, calculated = [], []
    coverage = {"eligible": False, "reason": "Select exact covered equipment to review membership discounts.", "discountRules": []}
    if unit:
        pseudo_job = SimpleNamespace(id=job.id if job else "invoice-preview", branch_id=site.branch_id, equipment_id=unit.id, property_id=site.id, customer_id=customer.id,
            data={"trade": p["trade"], "service": p["service"], "service_date": str(p["service_date"])})
        coverage = service_memberships.eligibility(db, actor, pseudo_job)
        if coverage.get("eligible") and not coverage["discountRules"]:
            legacy = agreements.coverage(db, actor, pseudo_job)
            if legacy.get("state") == "covered" and not legacy.get("portal_membership"):
                coverage["discountRules"] = [{"kind": k, "service": p["service"], "percent": legacy.get("discount", 0)} for k in ("labor", "material", "other")]
    for index, original in enumerate(p["lines"]):
        line = dict(original)
        q = Decimal(line["quantity"])
        if q <= 0 or q > 100000:
            raise Problem("Quantities must be positive and at most 100000.", 422)
        if line.get("pricebook_id"):
            if line["category"] == "credit":
                raise Problem("Credits require an explicit reviewed amount, not a pricebook record.", 422)
            sku = record(db, actor, line["pricebook_id"], "skus")
            if sku.branch_id != site.branch_id:
                raise Problem("Pricebook record belongs to another branch.", 422)
            line["unit_price"] = format(Decimal(sku.data["price_cents"]) / 100, ".2f")
            line["price_source"] = {"id": sku.id, "revision": sku.revision, "name": sku.name}
        if line["unit_price"] is not None:
            if line["category"] == "credit":
                line["unit_price"] = format(-abs(Decimal(line["unit_price"])), "f")
            elif Decimal(line["unit_price"]) < 0:
                raise Problem("Use the Credit category for a negative adjustment.", 422)
        gross = None if line["unit_price"] is None else int((q * cents(line["unit_price"])).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        if gross is None:
            issues.append(f"Line {index+1}: price required")
        percent = next((r["percent"] for r in coverage.get("discountRules", []) if r["kind"] == line["category"] and r["service"] == p["service"]), 0) if coverage.get("eligible") else 0
        if line["apply_membership"] and not percent:
            issues.append(f"Line {index+1}: selected membership adjustment is not eligible")
        proposed = int((Decimal(gross or 0)*percent/100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        applied = proposed if line["apply_membership"] else 0
        calculated.append(line | {"subtotal_cents": gross, "proposed_discount_cents": proposed, "discount_percent": percent,
            "discount_reason": coverage["reason"] + f" {line['category']} / {p['service']}: {percent}%",
            "discount_cents": applied, "total_cents": None if gross is None else gross-applied})
    subtotal = sum(l["subtotal_cents"] or 0 for l in calculated)
    reduction = sum(l["discount_cents"] for l in calculated)
    if subtotal - reduction < 0:
        issues.append("Credits exceed the invoice charges. Review before finalizing.")
    tax = None if config["tax_bps"] is None else int((Decimal(subtotal-reduction)*config["tax_bps"]/10000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if tax is None:
        issues.append("Configure the company tax rate before finalizing (explicit 0 is supported).")
    if not all(config["company"].values()):
        issues.append("Company name, address and contact are required before finalizing.")
    if not customer.name.strip() or not site.data.get("address", "").strip() or not (customer.data.get("email") or customer.data.get("phone")):
        issues.append("Customer name, service/billing address and email or phone are required.")
    if p["due_date"] < p["invoice_date"]:
        issues.append("Due date cannot precede the invoice date.")
    if not p["review_confirmed"]:
        issues.append("Confirm descriptions, categories, quantities, pricing and review questions.")
    if (p["missing_information"] or p["ambiguities"]) and not p["review_note"].strip():
        issues.append("Record how the missing information and ambiguities were resolved.")
    result = {"currency": "USD", "lines": calculated, "subtotal_cents": subtotal, "discount_cents": reduction,
        "tax_cents": tax, "total_cents": subtotal-reduction+(tax or 0), "partial": any(l["unit_price"] is None for l in calculated),
        "issues": issues, "can_finalize": not issues, "coverage": coverage, "configuration": config,
        "customer": {"id": customer.id, "name": customer.name, "email": customer.data.get("email", ""), "phone": customer.data.get("phone", "")},
        "property": {"id": site.id, "name": site.name, "address": site.data["address"]}}
    result["preview_token"] = hashlib.sha256(json.dumps([p,result], sort_keys=True, default=str).encode()).hexdigest()
    return result


def save(db, actor, p):
    draft = p["draft"]
    customer, site, _, _ = selection(db, actor, draft, "approve" if p["finalize"] else "write")
    row = db.get(Invoice, (actor.tenant, p["id"]))
    if row:
        actor.allow(row.branch_id, "approve" if p["finalize"] else "write")
        if row.proposal_id or row.status == "finalized":
            raise Problem("This invoice is immutable. Create a new draft for corrections.")
        if row.revision != p["expected_revision"]:
            raise Problem("Invoice changed. Reopen it before saving.")
    elif p["expected_revision"]:
        raise Problem("Invoice not found.", 404)
    result = preview(db, actor, draft)
    if p["finalize"] and p.get("preview_token") != result["preview_token"]:
        raise Problem("Pricing, membership or billing details changed. Refresh the preview and review again.")
    if p["finalize"] and result["issues"]:
        raise Problem("Cannot finalize: " + " · ".join(result["issues"]), 422)
    before = row.snapshot if row else None
    if not row:
        sequence = db.scalar(text("SELECT nextval('invoice_number_v1')"))
        row = Invoice(tenant_id=actor.tenant, branch_id=site.branch_id, id=p["id"], number=f"INV-{date.today().year}-{sequence:06d}", revision=0)
    elif row.branch_id != site.branch_id:
        raise Problem("An existing invoice cannot move between branches.", 422)
    history = (before or {}).get("review_changes", [])
    history = history + [{"actor": actor.subject, "date": date.today().isoformat(), "before": (before or {}).get("draft"), "after": draft}]
    row.customer_id, row.property_id, row.job_id = customer.id, site.id, draft.get("job_id")
    row.status, row.revision = ("finalized" if p["finalize"] else "draft"), row.revision+1
    row.snapshot = {"schema_version": 2, "draft": draft, "review_changes": history, **result}
    db.add(row); db.flush()
    event(db, actor, row.branch_id, "invoice."+row.status, row.id, {"revision": row.revision, "total_cents": result["total_cents"], "job_id": row.job_id})
    return dump(row)

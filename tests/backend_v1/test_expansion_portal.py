from datetime import date, timedelta


def test_lead_capture_conversion_and_scoped_lists(api):
    today = date.today()
    captured = api.request(
        "POST", "/leads",
        {"branch_id": "a", "name": "New lead", "address": "12 Main St",
         "email": "lead@example.com", "phone": "555-0100", "trade": "Electrical",
         "service": "inspection", "description": "Panel inspection requested"},
        expected=201,
    )
    lead = captured["lead"]
    assert lead["customer_id"] == captured["customer"]["id"]
    assert lead["property_id"] == captured["property"]["id"]
    assert lead["data"]["state"] == "reviewed"
    assert lead["id"] in {row["id"] for row in api.request("GET", "/records/opportunities")}
    cross_trade = api.request("POST", "/opportunities", {
        "branch_id": "a", "customer_id": lead["customer_id"],
        "property_id": lead["property_id"], "trade": "HVAC", "service": "maintenance",
        "description": "Offer HVAC service to this electrical customer",
    }, expected=201)
    assert cross_trade["customer_id"] == lead["customer_id"]
    assert cross_trade["data"]["trade"] == "HVAC"
    unit = api.create("equipment", "Main panel", {"trade": "Electrical"}, parent_id=lead["property_id"])
    converted = api.request(
        "POST", f"/opportunities/{lead['id']}/convert",
        {"equipment_id": unit["id"], "data": {"trade": "Electrical", "service": "inspection",
         "service_date": today.isoformat(), "customer_approved": False,
         "billing_mode": "unknown", "required_materials": [], "prerequisites": [],
         "lines": [], "currency": "USD"}},
    )
    assert converted["job_id"]
    assert api.request("GET", f"/records/jobs/{converted['job_id']}")["customer_id"] == lead["customer_id"]
    assert api.request("GET", "/records/opportunities", role="office")
    assert api.request("GET", "/records/opportunities", role="viewer")

    terms = {"starts": today.isoformat(), "ends": (today + timedelta(days=365)).isoformat(),
             "discount": 10, "description": "Annual panel service", "due_dates": [], "grant": 2}
    agreement = api.request("POST", "/agreements", {"equipment_id": unit["id"],
                            "trade": "Electrical", "service": "inspection", "terms": terms}, expected=201)
    agreements = api.request("GET", "/agreements")
    assert next(row for row in agreements if row["id"] == agreement["agreement"]["id"])["remaining"] == 2
    assert api.request("GET", "/agreements", role="office")

    staged = api.request("POST", "/imports", {"branch_id": "a", "rows": [
        {"source_id": "external-1", "kind": "customers", "name": "Imported customer",
         "data": {"email": "", "phone": ""}}]})
    assert staged["id"] in {row["id"] for row in api.request("GET", "/imports")}
    assert api.request("GET", "/imports", role="office")
    assert api.request("POST", "/leads", {"branch_id": "b", "name": "Denied",
           "address": "12 Main St", "trade": "Electrical", "service": "inspection",
           "description": "No branch access"}, role="office", expected=403)["error"]

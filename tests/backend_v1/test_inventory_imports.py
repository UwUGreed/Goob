from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone


def test_reservation_concurrency_and_transfer(api, scenario):
    s = scenario
    payload = {
        "action": "reserve",
        "quantity": 4,
        "sku_id": s["sku"]["id"],
        "location_id": s["location"]["id"],
        "job_id": s["job"]["id"],
        "reason": "Concurrent reserve",
    }
    with ThreadPoolExecutor(2) as pool:
        codes = list(
            pool.map(
                lambda _: (
                    api.client.post(
                        "/api/v1/inventory/commands", json=payload, headers=api.headers()
                    ).status_code
                ),
                range(2),
            )
        )
    assert sorted(codes) == [200, 409]
    truck = api.create("locations", "Truck", {"location_type": "truck"})
    s["stock"]("transfer", 2, destination_id=truck["id"])
    rows = api.request("GET", "/inventory/balances")
    assert sum(r["on_hand"] for r in rows) == 6
    api.request(
        "POST", "/inventory/commands", payload | {"action": "adjust", "quantity": -1}, expected=409
    )


def test_damaged_return_and_readiness(api, scenario):
    scenario["stock"]("damaged", 1, job_id=scenario["job"]["id"])
    assert api.request("GET", "/inventory/balances")[0]["on_hand"] == 6
    evaluation = api.request("GET", f"/jobs/{scenario['job']['id']}/readiness")
    assert evaluation["state"] == "blocked"
    assert any(
        c["id"] == "technician_qualification_and_availability" and c["state"] == "unknown"
        for c in evaluation["checks"]
    )


def test_import_reconciliation_duplicate_and_retry(api):
    today = datetime.now(timezone.utc).date()
    rows = [
        {"source_id": "c", "kind": "customers", "name": "Imported customer", "data": {}},
        {
            "source_id": "p",
            "kind": "properties",
            "name": "Home",
            "parent_source": "c",
            "data": {"address": "123 Test"},
        },
        {
            "source_id": "e",
            "kind": "equipment",
            "name": "Heat pump",
            "parent_source": "p",
            "data": {"trade": "HVAC"},
        },
        {
            "source_id": "a",
            "kind": "agreements",
            "name": "Care",
            "equipment_source": "e",
            "needs_review": "Source says two visits but history is missing.",
            "data": {
                "trade": "HVAC",
                "service": "maintenance",
                "terms": {
                    "starts": str(today),
                    "ends": str(today + timedelta(days=365)),
                    "discount": 10,
                    "description": "Imported terms",
                    "grant": 2,
                },
            },
        },
    ]
    staged = api.request("POST", "/imports", {"branch_id": "a", "rows": rows})
    assert len(staged["report"]["issues"]) == 1
    api.request("POST", f"/imports/{staged['id']}/commit", expected=409)
    replacement = rows[-1] | {
        "resolution": "Owner provided verified service history; one visit remains."
    }
    replacement["data"]["terms"]["grant"] = 1
    api.request("POST", f"/imports/{staged['id']}/rows/3", replacement)
    committed = api.request("POST", f"/imports/{staged['id']}/commit")
    again = api.request("POST", f"/imports/{staged['id']}/commit")
    assert committed == again
    assert committed["report"]["imported_count"] == 4
    agreement = committed["report"]["mapping"]["a"]
    assert api.request("GET", f"/agreements/{agreement}")["remaining"] == 1


def test_csv_import_bad_relationship_rolls_back(api):
    csv = "source_id,kind,name,data\nc,customers,CSV customer,{}\n"
    staged = api.request("POST", "/imports/csv", {"branch_id": "a", "csv": csv})
    api.request("POST", f"/imports/{staged['id']}/commit")
    assert len(api.request("GET", "/records/customers")) == 1
    rows = [
        {"source_id": "x", "kind": "customers", "name": "Should roll back", "data": {}},
        {
            "source_id": "y",
            "kind": "equipment",
            "name": "Invalid parent",
            "parent_source": "x",
            "data": {"trade": "HVAC"},
        },
    ]
    batch = api.request("POST", "/imports", {"branch_id": "a", "rows": rows})
    api.request("POST", f"/imports/{batch['id']}/commit", expected=404)
    assert len(api.request("GET", "/records/customers")) == 1

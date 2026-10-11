from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from operations.domain import agreements
from operations.persistence import models
from operations.persistence.database import sessions
from operations.persistence.models import Event, Terms


def test_benefit_dates_do_not_depend_on_server_timezone(api, scenario, monkeypatch):
    instant = datetime(2027, 1, 2, 0, 30, tzinfo=timezone.utc)

    class PreviousLocalDay(date):
        @classmethod
        def today(cls):
            return date(2027, 1, 1)

    monkeypatch.setattr(agreements, "date", PreviousLocalDay)
    monkeypatch.setattr(agreements, "now", lambda: instant)
    monkeypatch.setattr(models, "now", lambda: instant)
    created = api.request(
        "POST",
        "/agreements",
        {
            "equipment_id": scenario["plumbing"]["id"],
            "trade": "Plumbing",
            "service": "inspection",
            "terms": {
                "starts": "2027-01-02",
                "ends": "2027-12-31",
                "grant": 1,
                "discount": 0,
                "description": "UTC effective date",
            },
        },
        expected=201,
    )
    identifier = created["agreement"]["id"]
    assert api.request("GET", f"/agreements/{identifier}")["remaining"] == 1
    api.request(
        "POST",
        f"/agreements/{identifier}/commands",
        {
            "action": "adjust",
            "expected_revision": 1,
            "amount": 1,
            "reason": "Verify adjustment default uses the same UTC day",
        },
    )
    result = api.request("GET", f"/agreements/{identifier}")
    assert result["remaining"] == 2
    assert all(entry["effective_on"] == "2027-01-02" for entry in result["ledger"])


def test_cross_trade_benefit_and_frozen_upgrade(api, scenario, engine):
    today = datetime.now(timezone.utc).date()
    plumbing = api.request(
        "POST",
        "/agreements",
        {
            "equipment_id": scenario["plumbing"]["id"],
            "trade": "Plumbing",
            "service": "inspection",
            "terms": {
                "starts": str(today),
                "ends": str(today + timedelta(days=365)),
                "discount": 5,
                "description": "Plumbing only",
                "grant": 2,
            },
        },
        expected=201,
    )
    agreement = scenario["agreement"]["agreement"]["id"]
    old_terms = scenario["agreement"]["terms"]
    api.request(
        "POST",
        f"/agreements/{agreement}/commands",
        {
            "action": "upgrade",
            "expected_revision": 1,
            "reason": "Add future benefit",
            "terms": {
                "starts": str(today + timedelta(days=1)),
                "ends": str(today + timedelta(days=365)),
                "discount": 20,
                "description": "Upgraded terms",
                "grant": 1,
            },
        },
    )
    with sessions(engine)() as db:
        unchanged = db.get(Terms, (api.tenant, old_terms["id"]))
        assert str(unchanged.ends) == old_terms["ends"]
        assert unchanged.discount == 10
    assert api.request("GET", f"/agreements/{plumbing['agreement']['id']}")["remaining"] == 2
    assert api.request("GET", f"/jobs/{scenario['job']['id']}/coverage")["discount"] == 10


def test_remaining_allowance_is_not_an_overdue_schedule(api, scenario):
    owed = api.request("GET", "/obligations")[0]
    assert owed["remaining"] == 1
    assert owed["scheduled_service_due"] == []
    assert owed["schedule_defined"] is False


def test_incomplete_material_disposition_rolls_back(api, scenario):
    extraction = scenario["extraction"] | {"materials": [scenario["extraction"]["materials"][0]]}
    p = api.request(
        "POST",
        f"/jobs/{scenario['job']['id']}/proposals",
        {"note": scenario["note"], "expected_job_revision": 1, "extraction": extraction},
        expected=201,
    )
    api.request(
        "POST",
        f"/proposals/{p['id']}/review",
        {"action": "approve", "expected_revision": 1, "reason": "Attempt incomplete disposition"},
        expected=409,
    )
    assert api.request("GET", "/inventory/balances")[0]["on_hand"] == 6


def test_ai_quota_is_bounded_even_on_provider_failure(api, scenario, monkeypatch, engine):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_HOURLY_REQUEST_LIMIT", "1")
    path = f"/jobs/{scenario['job']['id']}/proposals"
    body = {"note": scenario["note"], "expected_job_revision": 1}
    api.request("POST", path, body, expected=503)
    api.request("POST", path, body, expected=429)
    with sessions(engine)() as db:
        attempts = db.scalars(
            select(Event).where(Event.tenant_id == api.tenant, Event.kind == "ai.attempt")
        ).all()
        assert len(attempts) == 1


def test_no_provider_call_without_idempotency_key(api, scenario):
    headers = api.headers()
    del headers["Idempotency-Key"]
    response = api.client.post(
        f"/api/v1/jobs/{scenario['job']['id']}/proposals",
        json={"note": scenario["note"], "expected_job_revision": 1},
        headers=headers,
    )
    assert response.status_code == 400


def test_opening_stock_import_and_duplicate_retry(api):
    rows = [
        {"source_id": "s", "kind": "skus", "name": "Part", "data": {}},
        {
            "source_id": "l",
            "kind": "locations",
            "name": "Warehouse",
            "data": {"location_type": "warehouse"},
        },
        {
            "source_id": "b",
            "kind": "stock",
            "name": "Opening",
            "data": {"sku_source": "s", "location_source": "l", "quantity": 9},
        },
    ]
    staged = api.request("POST", "/imports", {"branch_id": "a", "rows": rows})
    api.request("POST", f"/imports/{staged['id']}/commit")
    repeat = api.request("POST", "/imports", {"branch_id": "a", "rows": rows})
    assert repeat["id"] == staged["id"]
    assert api.request("GET", "/inventory/balances")[0]["on_hand"] == 9


def test_message_is_draft_and_no_provider_side_effect(api, scenario):
    result = api.request(
        "POST",
        "/message-drafts",
        {
            "branch_id": "a",
            "customer_id": scenario["customer"]["id"],
            "channel": "email",
            "text": "Your inspection is due.",
        },
    )
    assert result["delivery"] == "not_sent"
    assert result["state"] == "draft"


def test_legacy_converter_requires_review_and_preserves_source_balances(api):
    from scripts.reconcile_demo_export import convert

    source = {
        "simulation": True,
        "crm": {
            "customers": [{"id": "customer-1", "name": "Fictional Morgan"}],
            "equipment": [
                {
                    "id": "hvac-1",
                    "customer": "customer-1",
                    "property": "Fictional Oak Lane",
                    "trade": "HVAC",
                    "name": "Heat pump",
                }
            ],
        },
        "agreements": {
            "agreements": [
                {
                    "id": "care-v1",
                    "equipment": "hvac-1",
                    "trade": "HVAC",
                    "start": "2026-01-01",
                    "end": "2027-12-31",
                    "discount": 10,
                    "terms": "Fictional maintenance",
                    "remaining": 1,
                }
            ]
        },
        "inventory": [
            {"id": "capacitor", "name": "Capacitor", "cost": 1800, "price": 4500, "available": 6}
        ],
    }
    payload, report = convert(source, "a")
    staged = api.request("POST", "/imports", payload)
    assert staged["report"]["issues"]
    for index, row in enumerate(staged["rows"]):
        if row["needs_review"]:
            api.request(
                "POST",
                f"/imports/{staged['id']}/rows/{index}",
                row | {"resolution": "Verified fictional source and physical opening balance."},
            )
    committed = api.request("POST", f"/imports/{staged['id']}/commit")
    assert sum(r["on_hand"] for r in api.request("GET", "/inventory/balances")) == sum(
        report["opening_stock"].values()
    )
    agreement = committed["report"]["mapping"]["agreement:care-v1"]
    assert (
        api.request("GET", f"/agreements/{agreement}")["remaining"]
        == report["opening_benefits"]["care-v1"]
    )


def test_quarantined_stock_cannot_be_reserved(api, scenario):
    location = api.create("locations", "Quarantine", {"location_type": "quarantine"})
    payload = {
        "sku_id": scenario["sku"]["id"],
        "location_id": location["id"],
        "quantity": 1,
        "reason": "Quarantine test",
    }
    api.request("POST", "/inventory/commands", payload | {"action": "receive"})
    api.request(
        "POST",
        "/inventory/commands",
        payload | {"action": "reserve", "job_id": scenario["job"]["id"]},
        expected=409,
    )


def test_cross_branch_parent_link_cannot_be_smuggled(api, scenario):
    hidden = api.create("customers", "Hidden", {}, branch="b")
    api.request(
        "POST",
        "/records/customers",
        {"name": "New", "branch_id": "a", "parent_id": hidden["id"], "data": {}},
        role="office",
        expected=422,
    )


def test_runtime_readiness_checks_schema(api):
    assert api.client.get("/health/live").status_code == 200
    assert api.client.get("/health/ready").status_code == 200


def test_raw_request_size_limit(api):
    response = api.client.post(
        "/api/v1/records/customers", content=b"x" * 1000001, headers=api.headers()
    )
    assert response.status_code == 413


def test_archival_does_not_orphan_active_history(api, scenario):
    for kind, key in [("equipment", "unit"), ("skus", "sku"), ("locations", "location")]:
        api.request(
            "PATCH",
            f"/records/{kind}/{scenario[key]['id']}",
            {"expected_revision": 1, "archived": True},
            expected=409,
        )
    empty = api.create("customers", "Unused", {})
    assert api.request(
        "PATCH", f"/records/customers/{empty['id']}", {"expected_revision": 1, "archived": True}
    )["archived"]

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select, text

from operations.persistence.database import sessions
from operations.persistence.models import Invoice, Membership, Record


def propose(api, s, **overrides):
    return api.request(
        "POST",
        f"/jobs/{s['job']['id']}/proposals",
        {"note": s["note"], "expected_job_revision": 1, "extraction": s["extraction"], **overrides},
        role="tech",
        expected=201,
    )


def approve(api, p, **kwargs):
    return api.request(
        "POST",
        f"/proposals/{p['id']}/review",
        {"action": "approve", "expected_revision": 1, "reason": "Reviewed work and materials"},
        **kwargs,
    )


def test_full_workflow_persistence_and_retry(api, scenario, engine):
    p = propose(api, scenario)
    assert api.request("GET", f"/proposals/{p['id']}")["billing_preview"]["approved_cents"] == 18000
    approve(api, p, role="tech", expected=403)
    key = str(uuid4())
    first = approve(api, p, key=key)
    assert approve(api, p, key=key) == first
    assert first["state"] == "approved"
    assert api.request("GET", "/inventory/balances")[0]["on_hand"] == 7
    assert (
        api.request("GET", f"/agreements/{scenario['agreement']['agreement']['id']}")["remaining"]
        == 0
    )
    with sessions(engine)() as db:
        assert len(db.scalars(select(Invoice).where(Invoice.tenant_id == api.tenant)).all()) == 1
        assert db.get(Record, (api.tenant, scenario["job"]["id"])).data["work_state"] == "confirmed"
    opportunity = api.request("GET", "/records/opportunities")[0]
    data = {
        "trade": "Plumbing",
        "service": "repair",
        "service_date": str(datetime.now(timezone.utc).date()),
    }
    result = api.request(
        "POST",
        f"/opportunities/{opportunity['id']}/convert",
        {"equipment_id": scenario["plumbing"]["id"], "data": data},
    )
    repeat = api.request(
        "POST",
        f"/opportunities/{opportunity['id']}/convert",
        {"equipment_id": scenario["plumbing"]["id"], "data": data},
    )
    assert result["job_id"] == repeat["job_id"]
    report = api.request("GET", "/analytics")
    assert report["draft_overcharge_corrections_cents"] == 6000
    assert report["events"]["work.confirmed"] == 1


def test_concurrent_proposals_only_one_consumes(api, scenario):
    proposals = [propose(api, scenario), propose(api, scenario)]

    def run(p):
        return api.client.post(
            f"/api/v1/proposals/{p['id']}/review",
            json={"action": "approve", "expected_revision": 1, "reason": "Concurrency test"},
            headers=api.headers(),
        ).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(run, proposals)) == [200, 409]
    assert api.request("GET", "/inventory/balances")[0]["on_hand"] == 7


def test_atomic_rollback_on_late_failure(api, scenario, engine):
    p = propose(api, scenario)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE OR REPLACE FUNCTION goob_test_fail_invoice() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.tenant_id = TG_ARGV[0] THEN RAISE EXCEPTION 'test invoice failure'; END IF; RETURN NEW; END; $$"
            )
        )
        # UUID originates from this fixture, not user input.
        conn.execute(
            text(
                f"CREATE TRIGGER test_fail_invoice BEFORE INSERT ON invoices_v1 FOR EACH ROW EXECUTE FUNCTION goob_test_fail_invoice('{api.tenant}')"
            )
        )
    try:
        approve(api, p, expected=503)
        assert api.request("GET", "/inventory/balances")[0]["on_hand"] == 6
        assert (
            api.request("GET", f"/agreements/{scenario['agreement']['agreement']['id']}")[
                "remaining"
            ]
            == 1
        )
        assert api.request("GET", f"/proposals/{p['id']}")["proposal"]["state"] == "pending"
    finally:
        with engine.begin() as conn:
            conn.execute(text("DROP TRIGGER test_fail_invoice ON invoices_v1"))


def test_stale_job_and_changed_terms(api, scenario):
    p = propose(api, scenario)
    api.request(
        "PATCH",
        f"/records/jobs/{scenario['job']['id']}",
        {"expected_revision": 1, "name": "Updated"},
    )
    approve(api, p, expected=409)
    p = propose(api, scenario, expected_job_revision=2)
    api.request(
        "POST",
        f"/agreements/{scenario['agreement']['agreement']['id']}/commands",
        {
            "action": "adjust",
            "expected_revision": 1,
            "amount": 1,
            "reason": "Verified extra entitlement",
        },
    )
    approve(api, p, expected=409)


def test_nonmember_path_and_unknown_materials(api, scenario):
    data = scenario["job_data"] | {"billing_mode": "nonmember"}
    api.request(
        "PATCH", f"/records/jobs/{scenario['job']['id']}", {"expected_revision": 1, "data": data}
    )
    extraction = scenario["extraction"] | {"unknowns": ["Confirm catalog match"]}
    p = propose(api, scenario, expected_job_revision=2, extraction=extraction)
    approve(api, p, expected=409)
    revised = api.request(
        "POST",
        f"/proposals/{p['id']}/review",
        {
            "action": "revise",
            "expected_revision": 1,
            "reason": "Catalog verified",
            "extraction": scenario["extraction"],
        },
        role="tech",
    )
    approve(api, revised)
    invoice = api.request("GET", f"/jobs/{scenario['job']['id']}/history")["invoices"][0]
    assert invoice["snapshot"]["approved_cents"] == 19500
    assert (
        api.request("GET", f"/agreements/{scenario['agreement']['agreement']['id']}")["remaining"]
        == 1
    )


def test_reversal_restores_benefit_not_installed_stock(api, scenario):
    p = propose(api, scenario)
    approve(api, p)
    api.request("POST", f"/jobs/{scenario['job']['id']}/reverse", {"reason": "Correction required"})
    assert api.request("GET", "/inventory/balances")[0]["on_hand"] == 7
    assert (
        api.request("GET", f"/agreements/{scenario['agreement']['agreement']['id']}")["remaining"]
        == 1
    )
    assert len(api.request("GET", f"/jobs/{scenario['job']['id']}/history")["invoices"]) == 1
    invoice = api.request("GET", f"/jobs/{scenario['job']['id']}/history")["invoices"][0]
    api.request("GET", f"/invoices/{invoice['id']}/accounting-export", expected=409)
    assert api.request("GET", f"/proposals/{p['id']}")["billing_preview"] == invoice["snapshot"]


def test_auth_tenants_branches_revoke_and_idempotency(api, scenario, engine):
    assert api.client.get("/api/v1/me").status_code == 401
    assert api.client.get("/api/v1/me", headers=api.headers(expired=True)).status_code == 401
    api.request(
        "GET",
        f"/records/jobs/{scenario['job']['id']}",
        role="other",
        company=api.other,
        expected=404,
    )
    hidden = api.create("customers", "Branch B", {}, branch="b")
    api.request("GET", f"/records/customers/{hidden['id']}", role="tech", expected=403)
    api.request("GET", "/export", role="tech", expected=403)
    key = str(uuid4())
    p = {"branch_id": "a", "name": "One", "data": {}}
    api.request("POST", "/records/customers", p, key=key, expected=201)
    api.request("POST", "/records/customers", p | {"name": "Two"}, key=key, expected=409)
    with sessions(engine)() as db:
        db.get(Membership, (api.tenant, "tech")).active = False
        db.commit()
    api.request("GET", "/records/jobs", role="tech", expected=403)


def test_evidence_and_disabled_modules(api, scenario):
    bad = scenario["extraction"] | {
        "materials": [
            scenario["extraction"]["materials"][0] | {"source_quote": "Fabricated evidence"}
        ]
    }
    api.request(
        "POST",
        f"/jobs/{scenario['job']['id']}/proposals",
        {"note": scenario["note"], "expected_job_revision": 1, "extraction": bad},
        expected=409,
    )
    api.request("POST", "/admin/modules", {"enabled": ["workflow"]}, expected=409)
    api.request("POST", "/admin/modules", {"enabled": ["crm"]})
    api.request("GET", "/inventory/balances", expected=403)


def test_future_grants_do_not_cover_past_work(api, scenario):
    agreement = scenario["agreement"]["agreement"]["id"]
    starts = datetime.now(timezone.utc).date() + timedelta(days=366)
    api.request(
        "POST",
        f"/agreements/{agreement}/commands",
        {
            "action": "renew",
            "expected_revision": 1,
            "reason": "Renewal",
            "terms": {
                "starts": str(starts),
                "ends": str(starts + timedelta(days=365)),
                "discount": 15,
                "description": "Future terms",
                "grant": 2,
            },
        },
    )
    assert api.request("GET", f"/agreements/{agreement}")["remaining"] == 1

from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from operations.api_v1.app import create_app
from operations.persistence.readiness import SCHEMA_REVISION, check_schema
from scripts.backend_preflight import inspect
from scripts.check_backend import check, validate_url


def test_workspace_joins_persisted_job_context_without_writing(api, scenario):
    before = api.request("GET", "/export")
    balances = api.request("GET", "/inventory/balances")
    workspace = api.request("GET", f"/jobs/{scenario['job']['id']}/workspace")
    assert workspace["job"]["id"] == scenario["job"]["id"]
    assert workspace["customer"]["id"] == scenario["customer"]["id"]
    assert workspace["property"]["id"] == scenario["site"]["id"]
    assert workspace["equipment"]["id"] == scenario["unit"]["id"]
    assert workspace["coverage"]["remaining"] == 1
    assert workspace["parts"][0]["id"] == scenario["sku"]["id"]
    assert workspace["stock"][0]["available"] == 6
    assert workspace["locations"][0]["id"] == scenario["location"]["id"]
    assert workspace["reservations"][0]["state"] == "issued"
    assert workspace["readiness"]["state"] == "unknown"
    assert workspace["invoices"] == []
    after = api.request("GET", "/export")
    before.pop("exported_at")
    after.pop("exported_at")
    assert before == after
    assert balances == api.request("GET", "/inventory/balances")


def test_workspace_scopes_tenant_branch_modules_and_history_limit(api, scenario):
    path = f"/jobs/{scenario['job']['id']}/workspace"
    api.request("GET", path, role="other", company=api.other, expected=404)
    api.request(
        "POST", "/admin/members/viewer", {"role": "viewer", "branches": ["b"], "active": True}
    )
    api.request("GET", path, role="viewer", expected=403)
    scenario["stock"]("return", 1, job_id=scenario["job"]["id"])
    limited = api.request("GET", path + "?limit=1")
    assert limited["truncated"]["movements"] is True
    assert len(limited["movements"]) == 1
    api.request("GET", path + "?limit=101", expected=422)
    api.request("POST", "/admin/modules", {"enabled": ["crm", "jobs"]})
    api.request("GET", path, expected=403)


def test_workspace_shows_approved_snapshot_and_review_evidence(api, scenario):
    proposal = api.request(
        "POST",
        f"/jobs/{scenario['job']['id']}/proposals",
        {
            "note": scenario["note"],
            "expected_job_revision": 1,
            "extraction": scenario["extraction"],
        },
        expected=201,
    )
    api.request(
        "POST",
        f"/proposals/{proposal['id']}/review",
        {
            "action": "approve",
            "expected_revision": 1,
            "reason": "Verified fictional work",
        },
    )
    data = api.request("GET", f"/jobs/{scenario['job']['id']}/workspace")
    assert data["job"]["data"]["work_state"] == "confirmed"
    assert data["coverage"]["remaining"] == 0
    assert data["invoices"][0]["snapshot"]["approved_cents"] == 18000
    assert data["proposals"][0]["state"] == "approved"
    assert data["notes"][0]["text"] == scenario["note"]
    assert data["stock"][0]["available"] == 7
    assert data["events"]
    assert (
        check(api.client, api.headers(), scenario["job"]["id"])["passed"][-1]
        == "persisted_job_workspace"
    )


def test_schema_check_rejects_missing_revision_and_wrong_revision():
    for revisions in ([], ["old"], [SCHEMA_REVISION, "unexpected"]):
        connection = Mock()
        connection.scalars.return_value = revisions
        with pytest.raises(RuntimeError, match="revision"):
            check_schema(connection)
        connection.execute.assert_not_called()


def test_readiness_detects_a_missing_table_without_touching_cloud_app_tables(api, engine):
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE outbox_v1 RENAME TO temporarily_missing_outbox"))
    try:
        assert api.client.get("/health/live").status_code == 200
        assert api.client.get("/health/ready").status_code == 503
    finally:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE temporarily_missing_outbox RENAME TO outbox_v1"))
    assert api.client.get("/health/ready").status_code == 200


def test_browser_preflight_allows_only_the_configured_origin(engine, monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", " https://goob.example, https://other.example ")
    with TestClient(create_app(engine=engine, verifier=lambda _: "unused")) as client:
        headers = {
            "Origin": "https://goob.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,x-tenant-id,idempotency-key,content-type",
        }
        allowed = client.options("/api/v1/records/jobs", headers=headers)
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == "https://goob.example"
        denied = client.options(
            "/api/v1/records/jobs", headers=headers | {"Origin": "https://unknown.example"}
        )
        assert denied.status_code == 400
        assert "access-control-allow-origin" not in denied.headers


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://user:secret@example.com",
        "https://example.com/?token=secret",
        "file:///tmp/test",
        "http://127.0.0.1.evil.example",
        "https://example.com/api/v1",
    ],
)
def test_smoke_tool_will_not_send_bearer_tokens_to_unsafe_targets(url):
    with pytest.raises(ValueError):
        validate_url(url)


@pytest.mark.parametrize(
    "url", ["https://goob.example", "http://127.0.0.1:8090", "http://[::1]:8090/"]
)
def test_smoke_tool_accepts_https_or_loopback(url):
    assert validate_url(url) == url.rstrip("/")


def test_smoke_tool_rejects_frontend_html_instead_of_api_json():
    with httpx.Client(
        base_url="https://goob.example",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<html>fallback</html>")),
    ) as client:
        with pytest.raises(ValueError, match="non-JSON"):
            check(client, {})


def test_preflight_reports_missing_settings_without_leaking_values(monkeypatch):
    for key in (
        "GOOB_API_DATABASE_URL",
        "DATABASE_URL",
        "OIDC_ISSUER",
        "OIDC_JWKS_URL",
        "OIDC_AUDIENCE",
        "ALLOWED_ORIGINS",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DATABASE_URL", "secret-invalid-database-url")
    result = inspect(production=True)
    assert not result["configuration_passed"]
    assert "secret-invalid" not in str(result)
    assert result["tbd"] == ["Gemini", "ElevenLabs"]


def test_preflight_configured_is_not_claimed_as_live_acceptance(monkeypatch):
    monkeypatch.delenv("GOOB_API_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://runtime:fake-secret@cloud.example/test?sslmode=verify-full"
    )
    monkeypatch.setenv("GOOB_ENV", "production")
    monkeypatch.setenv("OIDC_ISSUER", "https://login.example/")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://login.example/jwks")
    monkeypatch.setenv("OIDC_AUDIENCE", "goob")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://goob.example")
    result = inspect(production=True)
    assert result["configuration_passed"]
    assert not result["database_checked"]
    assert result["still_requires"]
    assert "fake-secret" not in str(result)

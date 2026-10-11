import json
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from operations.api_v1.auth import OIDCVerifier
from operations.domain.common import Problem
from operations.integrations.gemini import Gemini
from scripts.backend_demo import run


def test_openapi_exposes_bearer_authorization_for_browser(api):
    schema = api.client.get("/api/v1/openapi.json").json()
    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }
    endpoint = schema["paths"]["/api/v1/me"]["get"]
    assert endpoint["security"] == [{"HTTPBearer": []}]
    assert all(p["name"].lower() != "authorization" for p in endpoint["parameters"])
    assert "security" not in schema["paths"]["/health/live"]["get"]


def extraction():
    return {
        "equipment_id": "equipment-1",
        "completed_work": "Maintenance",
        "completed": True,
        "materials": [],
        "followups": [],
        "unknowns": [],
    }


def test_gemini_sends_structured_request_and_tracks_usage(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": json.dumps(extraction())}]},
                    }
                ],
                "usageMetadata": {"totalTokenCount": 50},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result, metadata = Gemini(client).extract(
            "Maintenance completed", {"equipment_id": "equipment-1"}
        )
    assert result == extraction()
    body = json.loads(requests[0].content)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "responseJsonSchema" in body["generationConfig"]
    assert metadata["usage"]["totalTokenCount"] == 50
    assert requests[0].headers["x-goog-api-key"] == "test-key-not-real"
    assert "test-key-not-real" not in str(requests[0].url)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429, json={"error": "quota"}),
        httpx.Response(
            200,
            json={
                "candidates": [
                    {"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{}"}]}}
                ]
            },
        ),
        httpx.Response(
            200,
            json={
                "candidates": [
                    {"finishReason": "STOP", "content": {"parts": [{"text": "not-json"}]}}
                ]
            },
        ),
    ],
)
def test_provider_failures_never_become_fixed_demo_output(monkeypatch, response):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    with httpx.Client(transport=httpx.MockTransport(lambda _: response)) as client:
        with pytest.raises(Problem):
            Gemini(client).extract("Anything", {})


def test_absent_credentials_are_explicit(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(Problem) as caught:
        Gemini().extract("Anything", {})
    assert caught.value.status == 503


def test_real_oidc_verifier_checks_claims(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setenv("OIDC_ISSUER", "https://issuer.example/")
    monkeypatch.setenv("OIDC_AUDIENCE", "goob")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://issuer.example/jwks")
    verifier = OIDCVerifier()

    class Key:
        pass

    signing_key = Key()
    signing_key.key = key.public_key()
    monkeypatch.setattr(verifier.keys, "get_signing_key_from_jwt", lambda _: signing_key)
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "person",
        "iss": "https://issuer.example/",
        "aud": "goob",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    assert verifier(jwt.encode(claims, key, algorithm="RS256")) == "person"
    for override in [
        {"iss": "https://evil.example/"},
        {"aud": "wrong"},
        {"exp": now - timedelta(minutes=1)},
    ]:
        with pytest.raises(Problem):
            verifier(jwt.encode(claims | override, key, algorithm="RS256"))


def test_api_demo_uses_only_new_backend(api):
    def call(method, path, body=None):
        expected = (
            201
            if method == "POST"
            and (
                path.startswith("/records/") or path == "/agreements" or path.endswith("/proposals")
            )
            else 200
        )
        return api.request(method, path, body, expected=expected)

    result = run(call, "a")
    assert result["provider"] == "manual"
    assert result["billing_preview"]["approved_cents"] == 18000
    assert result["agreement"]["remaining"] == 0
    assert len(result["history"]["invoices"]) == 1

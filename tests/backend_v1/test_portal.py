from uuid import uuid4
from datetime import datetime, timezone
from operations.api_v1.portal_auth import password_hash
from operations.domain import desk
from operations.domain.common import Actor
from operations.persistence.database import sessions
from operations.persistence.models import PortalUser, DispatchTechnician
import pytest


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8090", "http://127.0.0.1:8090"])
def test_development_frontend_origins(api, monkeypatch, origin):
    monkeypatch.setenv("GOOB_ENV", "development")
    assert api.client.post("/api/auth/sign-out", json={}, headers={"Origin": origin, "Sec-Fetch-Site": "same-origin"}).status_code == 200
    assert api.client.post("/api/auth/sign-out", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert api.client.post("/api/auth/sign-out", json={}, headers={"Origin": origin, "Sec-Fetch-Site": "cross-site"}).status_code == 403
    monkeypatch.setenv("GOOB_ENV", "production")
    monkeypatch.delenv("GOOB_PUBLIC_ORIGIN", raising=False)
    assert api.client.post("/api/auth/sign-out", json={}, headers={"Origin": origin}).status_code == 403


def test_cloud_portal_login_crud_assignment_stock_and_signout(api, engine):
    password = "test-only-long-password"
    with sessions(engine)() as db:
        db.add(PortalUser(id=str(uuid4()), identifier="portal-"+api.tenant+"@test.local", password_hash=password_hash(password), tenant_id=api.tenant, subject="owner", demo=True))
        actor = Actor(api.tenant, "owner", "owner", ("a", "b"))
        location = desk.create(db, actor, "locations", "a", "P-02", {"location_type": "truck"})
        db.add(DispatchTechnician(tenant_id=api.tenant, id="maya", branch_id="a", name="Maya Chen", trade="Plumbing", location_id=location.id, node="0-3", status="Available"))
        db.commit()
    client = api.client
    assert client.get("/api/dispatch").status_code == 401
    assert client.post("/api/auth/sign-in", json={"identifier":"portal-"+api.tenant+"@test.local","password":"incorrect"}).status_code == 401
    response = client.post("/api/auth/sign-in", json={"identifier":"portal-"+api.tenant+"@test.local","password":password})
    assert response.status_code == 200, response.text
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.get("/api/auth/session").status_code == 200

    def change(body, status=200):
        result = client.post("/api/dispatch", json=body, headers={"Idempotency-Key":str(uuid4())})
        assert result.status_code == status, result.text
        return result.json().get("state")

    state = change({"type":"customer","customer":{"id":str(uuid4()),"name":"Cloud verification","email":"test@example.com","phone":"","address":"124 Oak Lane"}})
    customer = next(c for c in state["customers"] if c["name"] == "Cloud verification")
    state = change({"type":"stock","item":{"id":str(uuid4()),"part":"Valve","sku":"PORTAL-VALVE","trade":"Plumbing","truck":"P-02","quantity":3,"threshold":1}})
    item = next(i for i in state["stock"] if i["part"] == "Valve")
    change({"type":"stock","item":item|{"quantity":-1}},422)
    job_id="job-"+str(uuid4())
    state=change({"type":"create","job":{"id":job_id,"customerId":customer["id"],"title":"Sink leak","description":"Database verification","address":"124 Oak Lane","trade":"Plumbing","part":"Valve","node":"1-0","time":"Today","urgent":True}})
    start=int(datetime(2026,10,10,10,45,tzinfo=timezone.utc).timestamp()*1000)
    state=change({"type":"assign","jobId":job_id,"techId":"maya","slot":{"date":"2026-10-10","start":start,"end":start+3600000,"travelStart":start-600000}})
    assert state["jobs"][job_id]=="Assigned"
    assert state["reservations"][0]["quantity"]==1
    change({"type":"stock","item":item|{"quantity":0}},409)
    for action in ["start","pause","start","arrive","work","complete"]:
        state=change({"type":action,"techId":"maya"})
    assert state["jobs"][job_id]=="Completed"
    assert next(i for i in state["stock"] if i["id"]==item["id"])["quantity"]==2
    assert state["reservations"]==[]
    assert client.get("/api/dispatch").json()["state"]["jobs"][job_id]=="Completed"
    assert client.post("/api/dispatch",json={"type":"complete","techId":"maya"},headers={"Origin":"https://evil.example"}).status_code==403
    token=dict(client.cookies)
    assert client.post("/api/auth/sign-out",json={}).status_code==200
    client.cookies.update(token)
    assert client.get("/api/auth/session").status_code==401

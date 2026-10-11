import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from alembic import command as migrations
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from operations.api_v1.app import create_app
from operations.domain.common import Problem
from operations.persistence.database import engine_for, sessions
from operations.persistence.models import Branch, Membership, Tenant


@pytest.fixture(scope="session")
def engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set TEST_DATABASE_URL explicitly; tests never use the app's cloud URL implicitly."
        )
    e = engine_for(url)
    schema = "goob_test_v1_" + uuid4().hex
    with e.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    e.dispose()

    @event.listens_for(e, "connect")
    def isolate(connection, _record):
        previous = connection.autocommit
        connection.autocommit = True
        try:
            with connection.cursor() as cursor:
                cursor.execute(f'SET search_path TO "{schema}", pg_catalog')
        finally:
            connection.autocommit = previous

    try:
        with e.connect() as connection:
            config = Config("alembic-backend.ini")
            config.attributes["connection"] = connection
            migrations.upgrade(config, "head")
        yield e
    finally:
        with e.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        e.dispose()


@pytest.fixture
def api(engine):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key()
    tenant, other = str(uuid4()), str(uuid4())
    with sessions(engine)() as db:
        db.add_all([Tenant(id=tenant, name="Fictional Goob Test"), Tenant(id=other, name="Other")])
        db.flush()
        db.add_all(
            [
                Branch(tenant_id=tenant, id="a", name="A"),
                Branch(tenant_id=tenant, id="b", name="B"),
                Branch(tenant_id=other, id="a", name="A"),
            ]
        )
        db.flush()
        for subject, role, branches in [
            ("owner", "owner", ["a", "b"]),
            ("office", "office", ["a"]),
            ("tech", "technician", ["a"]),
            ("viewer", "viewer", ["a"]),
        ]:
            db.add(Membership(tenant_id=tenant, subject=subject, role=role, branches=branches))
        db.add(Membership(tenant_id=other, subject="other", role="owner", branches=["a"]))
        db.commit()

    def verify(token):
        try:
            return jwt.decode(
                token,
                public,
                algorithms=["RS256"],
                audience="goob-tests",
                issuer="https://identity.test",
                options={"require": ["sub", "exp", "iat"]},
            )["sub"]
        except jwt.PyJWTError as exc:
            raise Problem("Invalid token", 401) from exc

    class API:
        def __init__(self):
            self.client = TestClient(create_app(engine=engine, verifier=verify))
            self.tenant = tenant
            self.other = other

        def headers(self, role="owner", key=None, company=None, expired=False):
            now = datetime.now(timezone.utc)
            token = jwt.encode(
                {
                    "sub": role,
                    "iss": "https://identity.test",
                    "aud": "goob-tests",
                    "iat": now - timedelta(minutes=5),
                    "exp": now + timedelta(minutes=-1 if expired else 5),
                },
                private,
                algorithm="RS256",
            )
            return {
                "Authorization": "Bearer " + token,
                "X-Tenant-ID": company or tenant,
                "Idempotency-Key": key or str(uuid4()),
            }

        def request(
            self, method, path, body=None, role="owner", expected=200, key=None, company=None
        ):
            response = self.client.request(
                method, "/api/v1" + path, json=body, headers=self.headers(role, key, company)
            )
            assert response.status_code == expected, response.text
            return response.json()

        def create(self, kind, name, data, branch="a", **links):
            return self.request(
                "POST",
                "/records/" + kind,
                {"name": name, "branch_id": branch, "data": data, **links},
                expected=201,
            )

    result = API()
    yield result
    result.client.close()


@pytest.fixture
def scenario(api):
    today = datetime.now(timezone.utc).date()
    customer = api.create("customers", "Morgan", {})
    site = api.create("properties", "Home", {"address": "124 Oak Lane"}, parent_id=customer["id"])
    unit = api.create("equipment", "Upstairs heat pump", {"trade": "HVAC"}, parent_id=site["id"])
    plumbing = api.create(
        "equipment", "Kitchen plumbing", {"trade": "Plumbing"}, parent_id=site["id"]
    )
    sku = api.create(
        "skus", "Capacitor", {"price_cents": 4500, "cost_cents": 1800, "barcode": str(uuid4())}
    )
    location = api.create("locations", "Warehouse", {"location_type": "warehouse"})
    job_data = {
        "trade": "HVAC",
        "service": "maintenance",
        "service_date": str(today),
        "customer_approved": True,
        "billing_mode": "membership",
        "required_materials": [{"sku_id": sku["id"], "quantity": 2}],
        "lines": [
            {
                "description": "Labor",
                "kind": "labor",
                "quantity": 1,
                "unit_cents": 15000,
                "discount_eligible": True,
            },
            {
                "description": "Capacitors",
                "kind": "material",
                "sku_id": sku["id"],
                "quantity": 2,
                "unit_cents": 4500,
            },
        ],
    }
    job = api.create(
        "jobs",
        "Maintenance",
        job_data,
        customer_id=customer["id"],
        property_id=site["id"],
        equipment_id=unit["id"],
    )
    agreement = api.request(
        "POST",
        "/agreements",
        {
            "equipment_id": unit["id"],
            "trade": "HVAC",
            "service": "maintenance",
            "terms": {
                "starts": str(today - timedelta(days=1)),
                "ends": str(today + timedelta(days=365)),
                "discount": 10,
                "description": "One maintenance visit; labor discount",
                "grant": 1,
            },
        },
        expected=201,
    )

    def stock(action, quantity, **extra):
        return api.request(
            "POST",
            "/inventory/commands",
            {
                "action": action,
                "quantity": quantity,
                "sku_id": sku["id"],
                "location_id": location["id"],
                "reason": "Test evidence",
                **extra,
            },
        )

    stock("receive", 8)
    reservation = stock("reserve", 2, job_id=job["id"])["reservation_id"]
    stock("issue", 2, job_id=job["id"], reservation_id=reservation)
    note = "Maintenance completed. Installed one capacitor and returned the spare. Kitchen faucet leaks."
    extraction = {
        "equipment_id": unit["id"],
        "completed_work": "Maintenance",
        "completed": True,
        "materials": [
            {
                "sku_id": sku["id"],
                "location_id": location["id"],
                "quantity": 1,
                "disposition": "installed",
                "source_quote": "Installed one capacitor",
            },
            {
                "sku_id": sku["id"],
                "location_id": location["id"],
                "quantity": 1,
                "disposition": "unused_return",
                "source_quote": "returned the spare",
            },
        ],
        "followups": [
            {
                "trade": "Plumbing",
                "description": "Inspect kitchen faucet",
                "source_quote": "Kitchen faucet leaks.",
            }
        ],
        "unknowns": [],
    }
    return locals() | {"stock": stock}

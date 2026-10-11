"""Add a separate fictional demo workspace through the existing ORM/domain flow."""
import json
import os
import secrets
import argparse
from pathlib import Path
from sqlalchemy import select
from operations.api_v1.portal_auth import password_hash
from operations.domain import desk
from operations.domain.common import Actor
from operations.persistence.database import engine_for, sessions
from operations.persistence.models import Branch, DispatchTechnician, Membership, PortalUser, Tenant, uid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--identifier", default="goob")
    parser.add_argument("--credentials-file", default=".demo-credentials.json")
    args = parser.parse_args()
    engine = engine_for()
    if os.environ.get("GOOB_ENV") == "production":
        raise RuntimeError("Demo provisioning is restricted to development/demo environments.")
    destination = Path(args.credentials_file).resolve()
    identifier = args.identifier.strip().casefold()
    with sessions(engine)() as db:
        if db.scalar(select(PortalUser).where(PortalUser.identifier == identifier)):
            print("Existing demo account retained; credentials were not changed.")
            return
        if destination.exists():
            raise RuntimeError("Credential file exists without its database account; review before provisioning.")
        tenant, branch, subject = uid(), uid(), "portal-demo-"+uid()
        password = secrets.token_urlsafe(24)
        db.add(Tenant(id=tenant, name="Goob demo · fictional operations"))
        db.flush()
        db.add(Branch(tenant_id=tenant, id=branch, name="Columbia demo"))
        db.flush()
        db.add(Membership(tenant_id=tenant, subject=subject, role="owner", branches=[branch]))
        db.flush()
        db.add(PortalUser(id=uid(), identifier=identifier, password_hash=password_hash(password), tenant_id=tenant, subject=subject, demo=True))
        actor = Actor(tenant=tenant, subject=subject, role="owner", branches=[branch])
        desk.create(db, actor, "locations", branch, "Warehouse", {"location_type": "warehouse"})
        for name, trade, truck, node, issue, address, part in [
            ("Maya Chen", "Plumbing", "P-02", "0-3", "Kitchen sink leak", "124 Oak Lane", "Shut-off valve"),
            ("Jordan Ellis", "HVAC", "H-01", "1-3", "AC not cooling", "820 Pine St", "Run capacitor"),
            ("Leo Brooks", "Electrical", "E-03", "2-3", "Panel inspection", "200 Cedar Way", "Circuit breaker"),
        ]:
            location = desk.create(db, actor, "locations", branch, truck, {"location_type": "truck"})
            db.add(DispatchTechnician(tenant_id=tenant, id=uid(), branch_id=branch, name=name, trade=trade, location_id=location.id, node=node, status="Available"))
            desk.run(db, actor, {"type": "stock", "item": {"id": uid(), "part": part, "sku": "DEMO-"+truck, "trade": trade, "truck": truck, "quantity": 4, "threshold": 1}})
            customer = desk.create(db, actor, "customers", branch, "Demo customer · "+name.split()[0], {"email": "", "phone": ""})
            desk.run(db, actor, {"type": "create", "job": {"id": "job-"+uid(), "customerId": customer.id, "title": issue, "description": "Fictional demo visit. Route destination is simulated.", "address": address, "trade": trade, "part": part, "node": {"Plumbing":"1-0", "HVAC":"3-1", "Electrical":"2-2"}[trade], "urgent": trade == "Plumbing", "time": "Today"}})
        # Write credentials before committing, with owner-only permissions where supported.
        with destination.open("x", encoding="utf-8") as output:
            os.chmod(destination, 0o600)
            json.dump({"identifier": identifier, "password": password}, output)
        try:
            db.commit()
        except Exception:
            destination.unlink()
            raise
    print("Dedicated cloud demo workspace created. Credentials saved to the requested private file.")


if __name__ == "__main__":
    main()

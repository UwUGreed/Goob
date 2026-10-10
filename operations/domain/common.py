import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select, text

from operations.persistence.models import Command, Event, Record, Tenant


class Problem(Exception):
    def __init__(self, message, status=409):
        self.message, self.status = message, status


@dataclass(frozen=True)
class Actor:
    tenant: str
    subject: str
    role: str
    branches: tuple[str, ...]

    def allow(self, branch, action="read"):
        permissions = {
            "owner": {"read", "write", "propose", "approve", "admin"},
            "office": {"read", "write", "propose", "approve"},
            "technician": {"read", "propose"},
            "viewer": {"read"},
        }
        if branch not in self.branches or action not in permissions.get(self.role, set()):
            raise Problem("Not authorized for this branch or action.", 403)


def module(db, actor, name):
    from operations.domain.identity import DEPENDENCIES

    tenant = db.get(Tenant, actor.tenant)
    if not tenant or name not in tenant.modules:
        raise Problem("Module unavailable.", 403)
    for dependency in DEPENDENCIES.get(name, []):
        module(db, actor, dependency)


def get(db, actor, model, identifier, action="read", lock=False):
    q = select(model).where(model.tenant_id == actor.tenant, model.id == identifier)
    row = db.scalar(q.with_for_update() if lock else q)
    if row is None:
        raise Problem("Record not found.", 404)
    actor.allow(row.branch_id, action)
    return row


def record(db, actor, identifier, kind=None, action="read", lock=False):
    row = get(db, actor, Record, identifier, action, lock)
    if (kind and row.kind != kind) or row.archived:
        raise Problem("Record unavailable.", 404)
    return row


def dump(row):
    return {
        c.name: (v.isoformat() if isinstance(v := getattr(row, c.name), (date, datetime)) else v)
        for c in row.__table__.columns
    }


def event(db, actor, branch, kind, resource, evidence):
    db.add(
        Event(
            tenant_id=actor.tenant,
            branch_id=branch,
            kind=kind,
            actor=actor.subject,
            resource_id=resource,
            evidence=json.loads(json.dumps(evidence, default=str)),
        )
    )


def command(db, actor, key, operation, payload, run):
    if not key or len(key) > 160:
        raise Problem("Idempotency-Key of 1–160 characters is required.", 400)
    fingerprint = hashlib.sha256(
        json.dumps([actor.subject, operation, payload], sort_keys=True, default=str).encode()
    ).hexdigest()
    # Tenant serialization is intentionally conservative for a bounded pilot.
    # All mutation commands take the same transaction lock, including background work.
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:tenant, 0))"), {"tenant": actor.tenant}
    )
    db.expire_all()
    from operations.domain.identity import actor_for

    if actor_for(db, actor.tenant, actor.subject) != actor:
        raise Problem("Access changed; retry with current authorization.", 403)
    for name in db.info.get("required_modules", []):
        module(db, actor, name)
    existing = db.get(Command, (actor.tenant, key))
    if existing:
        if existing.fingerprint != fingerprint:
            raise Problem("Idempotency key was already used for a different request.")
        return existing.result
    result = json.loads(json.dumps(run(), default=str))
    db.flush()
    db.add(Command(tenant_id=actor.tenant, key=key, fingerprint=fingerprint, result=result))
    return result

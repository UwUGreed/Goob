from sqlalchemy import select

from operations.domain.common import Actor, Problem
from operations.persistence.models import Branch, Membership, Tenant

DEPENDENCIES = {
    "crm": [],
    "jobs": ["crm"],
    "inventory": ["jobs"],
    "agreements": ["crm"],
    "billing": ["jobs"],
    "workflow": ["jobs", "inventory", "agreements", "billing"],
    "imports": ["crm", "agreements"],
    "readiness": ["workflow"],
    "opportunities": ["jobs"],
    "analytics": ["workflow"],
}


def actor_for(db, tenant, subject):
    membership = db.get(Membership, (tenant, subject), populate_existing=True)
    if not membership or not membership.active:
        raise Problem("No active membership for this company.", 403)
    return Actor(tenant, subject, membership.role, tuple(membership.branches))


def update_member(db, actor, subject, p):
    if actor.role != "owner":
        raise Problem("Owner permission required.", 403)
    branches = set(db.scalars(select(Branch.id).where(Branch.tenant_id == actor.tenant)))
    if not set(p["branches"]) <= branches or not set(p["branches"]) <= set(actor.branches):
        raise Problem("Cannot grant access to branches outside your scope.", 403)
    existing = db.get(Membership, (actor.tenant, subject))
    if existing and not set(existing.branches) <= set(actor.branches):
        raise Problem("Cannot administer a user outside your branch scope.", 403)
    if subject == actor.subject and (
        p["role"] != "owner" or not p["active"] or set(p["branches"]) != set(actor.branches)
    ):
        raise Problem("An owner cannot revoke or reduce their own access.")
    if not existing:
        existing = Membership(tenant_id=actor.tenant, subject=subject)
        db.add(existing)
    existing.role, existing.branches, existing.active = p["role"], p["branches"], p["active"]
    return {"subject": subject, **p}


def configure(db, actor, modules):
    if actor.role != "owner":
        raise Problem("Owner permission required.", 403)
    all_branches = set(db.scalars(select(Branch.id).where(Branch.tenant_id == actor.tenant)))
    if set(actor.branches) != all_branches:
        raise Problem("Tenant module configuration requires access to all branches.", 403)
    if len(modules) != len(set(modules)) or set(modules) - DEPENDENCIES.keys():
        raise Problem("Invalid module list.", 422)
    for name in modules:
        if not set(DEPENDENCIES[name]) <= set(modules):
            raise Problem(f"Missing dependencies for {name}.")
    db.get(Tenant, actor.tenant).modules = modules
    return {"modules": modules, "data_preserved": True}

"""Read-only job context for clients adopting the authenticated API."""

from sqlalchemy import select

from operations.domain import agreements, readiness
from operations.domain.common import dump, module, record
from operations.persistence.models import (
    Balance,
    Event,
    Invoice,
    Movement,
    Note,
    Proposal,
    Record,
    Reservation,
    now,
)


def read(db, actor, identifier, limit=50):
    module(db, actor, "readiness")  # Includes workflow and its required modules.
    job = record(db, actor, identifier, "jobs")
    result = {
        "schema_version": 1,
        "read_at": now().isoformat(),
        "job": dump(job),
        "customer": dump(record(db, actor, job.customer_id, "customers")),
        "property": dump(record(db, actor, job.property_id, "properties")),
        "equipment": dump(record(db, actor, job.equipment_id, "equipment")),
        "coverage": agreements.coverage(db, actor, job),
        "readiness": readiness.evaluate(db, actor, job.id),
        "truncated": {},
    }

    def collect(name, model, condition, order):
        rows = db.scalars(
            select(model)
            .where(
                model.tenant_id == actor.tenant,
                model.branch_id == job.branch_id,
                condition,
            )
            .order_by(*order)
            .limit(limit + 1)
        ).all()
        result["truncated"][name] = len(rows) > limit
        result[name] = [dump(row) for row in rows[:limit]]

    for name, model in [
        ("notes", Note),
        ("invoices", Invoice),
        ("movements", Movement),
    ]:
        collect(name, model, model.job_id == job.id, [model.created_at.desc(), model.id])
    collect("proposals", Proposal, Proposal.job_id == job.id, [Proposal.id])
    collect("reservations", Reservation, Reservation.job_id == job.id, [Reservation.id])
    collect("events", Event, Event.resource_id == job.id, [Event.created_at.desc(), Event.id])

    # Required parts plus any parts actually moved/reserved for this job, including
    # rows outside the history window. Never pull another branch's inventory.
    needed = {item["sku_id"] for item in job.data["required_materials"]}
    moved = select(Movement.sku_id).where(
        Movement.tenant_id == actor.tenant, Movement.job_id == job.id
    )
    reserved = select(Reservation.sku_id).where(
        Reservation.tenant_id == actor.tenant, Reservation.job_id == job.id
    )
    collect(
        "parts",
        Record,
        (Record.kind == "skus")
        & (Record.id.in_(needed) | Record.id.in_(moved) | Record.id.in_(reserved)),
        [Record.name, Record.id],
    )
    collect(
        "stock",
        Balance,
        Balance.sku_id.in_(needed) | Balance.sku_id.in_(moved) | Balance.sku_id.in_(reserved),
        [Balance.sku_id, Balance.location_id],
    )
    for row in result["stock"]:
        row["available"] = row["on_hand"] - row["reserved"]
    location_ids = {
        row["location_id"] for row in result["stock"] + result["reservations"] + result["movements"]
    }
    collect(
        "locations", Record, (Record.kind == "locations") & Record.id.in_(location_ids), [Record.id]
    )
    return result

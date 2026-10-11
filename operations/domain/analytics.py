from sqlalchemy import func, select

from operations.persistence.models import Event, Invoice, Movement


def report(db, actor, start, end):
    movements = db.execute(
        select(
            func.date_trunc("day", Movement.created_at).label("day"),
            Movement.kind,
            func.sum(Movement.quantity).label("quantity"),
        )
        .where(
            Movement.tenant_id == actor.tenant,
            Movement.branch_id.in_(actor.branches),
            Movement.created_at >= start,
            Movement.created_at < end,
        )
        .group_by("day", Movement.kind)
        .order_by("day")
    ).all()
    invoices = db.scalars(
        select(Invoice).where(
            Invoice.tenant_id == actor.tenant,
            Invoice.branch_id.in_(actor.branches),
            Invoice.created_at >= start,
            Invoice.created_at < end,
        )
    ).all()
    events = db.execute(
        select(Event.kind, func.count())
        .where(
            Event.tenant_id == actor.tenant,
            Event.branch_id.in_(actor.branches),
            Event.created_at >= start,
            Event.created_at < end,
        )
        .group_by(Event.kind)
    ).all()
    return {
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "daily_material_movements": [
            {"day": day.isoformat(), "kind": kind, "quantity": qty} for day, kind, qty in movements
        ],
        "draft_overcharge_corrections_cents": sum(
            max(0, i.snapshot["original_cents"] - i.snapshot["approved_cents"]) for i in invoices
        ),
        "events": dict(events),
        "interpretation": "Draft corrections, not collected revenue or measured customer savings. Reversed approvals remain historical events.",
    }

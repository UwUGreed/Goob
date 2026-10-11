from sqlalchemy import func, select

from operations.domain.common import Problem, dump, event, get, record
from operations.persistence.models import Balance, Movement, Reservation, uid


def stock(db, actor, sku_id, location_id):
    sku = record(db, actor, sku_id, "skus")
    location = record(db, actor, location_id, "locations")
    if sku.branch_id != location.branch_id:
        raise Problem("SKU and location must belong to the same branch.")
    row = db.scalar(
        select(Balance)
        .where(
            Balance.tenant_id == actor.tenant,
            Balance.sku_id == sku_id,
            Balance.location_id == location_id,
        )
        .with_for_update()
    )
    if not row:
        row = Balance(
            tenant_id=actor.tenant,
            id=uid(),
            branch_id=location.branch_id,
            sku_id=sku_id,
            location_id=location_id,
            on_hand=0,
            reserved=0,
        )
        db.add(row)
        db.flush()
    return row


def movement(db, actor, balance, job_id, kind, quantity, delta, reason):
    if balance.on_hand + delta < balance.reserved:
        raise Problem("Insufficient unreserved stock.")
    balance.on_hand += delta
    row = Movement(
        tenant_id=actor.tenant,
        id=uid(),
        branch_id=balance.branch_id,
        sku_id=balance.sku_id,
        location_id=balance.location_id,
        job_id=job_id,
        kind=kind,
        quantity=quantity,
        delta=delta,
        reason=reason,
    )
    db.add(row)
    return row


def outstanding(db, actor, job_id, sku_id, location_id):
    rows = db.execute(
        select(Movement.kind, func.sum(Movement.quantity))
        .where(
            Movement.tenant_id == actor.tenant,
            Movement.job_id == job_id,
            Movement.sku_id == sku_id,
            Movement.location_id == location_id,
        )
        .group_by(Movement.kind)
    ).all()
    counts = dict(rows)
    return counts.get("issue", 0) - sum(
        counts.get(k, 0) for k in ["installed", "unused_return", "damaged"]
    )


def dispose(db, actor, job, entry):
    b = stock(db, actor, entry["sku_id"], entry["location_id"])
    if b.branch_id != job.branch_id:
        raise Problem("Material location is outside the job branch.")
    if outstanding(db, actor, job.id, b.sku_id, b.location_id) < entry["quantity"]:
        raise Problem("Material disposition exceeds outstanding issued quantity.")
    movement(
        db,
        actor,
        b,
        job.id,
        entry["disposition"],
        entry["quantity"],
        entry["quantity"] if entry["disposition"] == "unused_return" else 0,
        entry.get("source_quote", "Employee confirmed disposition"),
    )
    db.flush()


def execute(db, actor, p):
    b = stock(db, actor, p["sku_id"], p["location_id"])
    actor.allow(b.branch_id, "write")
    job = record(db, actor, p["job_id"], "jobs") if p.get("job_id") else None
    if job and (job.branch_id != b.branch_id or job.data.get("work_state") == "confirmed"):
        raise Problem("Job is confirmed or outside this branch.")
    action, qty = p["action"], p["quantity"]
    if (
        action in {"reserve", "issue"}
        and record(db, actor, b.location_id, "locations").data["location_type"] == "quarantine"
    ):
        raise Problem("Quarantined stock cannot be reserved or issued.")
    if action not in {"threshold", "adjust", "release"} and qty <= 0:
        raise Problem("Positive quantity required.", 422)
    reservation_id = None
    if action in {"reserve", "issue", "return", "damaged"} and not job:
        raise Problem("Job ID required.", 422)
    if action == "receive":
        movement(db, actor, b, None, "receive", qty, qty, p["reason"])
    elif action == "transfer":
        target = stock(db, actor, p["sku_id"], p["destination_id"])
        actor.allow(target.branch_id, "write")
        if target.id == b.id:
            raise Problem("Transfer requires different locations.")
        movement(db, actor, b, None, "transfer_out", qty, -qty, p["reason"])
        movement(db, actor, target, None, "transfer_in", qty, qty, p["reason"])
    elif action == "reserve":
        if b.on_hand - b.reserved < qty:
            raise Problem("Insufficient available stock.")
        b.reserved += qty
        r = Reservation(
            tenant_id=actor.tenant,
            id=uid(),
            branch_id=b.branch_id,
            sku_id=b.sku_id,
            location_id=b.location_id,
            job_id=job.id,
            quantity=qty,
        )
        reservation_id = r.id
        db.add(r)
    elif action in {"release", "issue"}:
        r = get(db, actor, Reservation, p["reservation_id"], "write", True)
        if r.state != "active" or r.sku_id != b.sku_id or r.location_id != b.location_id:
            raise Problem("Reservation is inactive or does not match the stock.")
        if action == "issue" and (r.job_id != job.id or qty != r.quantity):
            raise Problem("Issue must match the reserved job and quantity.")
        b.reserved -= r.quantity
        r.state = "released" if action == "release" else "issued"
        if action == "issue":
            movement(db, actor, b, job.id, "issue", qty, -qty, p["reason"])
    elif action in {"return", "damaged"}:
        dispose(
            db,
            actor,
            job,
            {
                "sku_id": b.sku_id,
                "location_id": b.location_id,
                "quantity": qty,
                "disposition": "unused_return" if action == "return" else "damaged",
                "source_quote": p["reason"],
            },
        )
    elif action == "adjust":
        movement(db, actor, b, None, "adjust", abs(qty), qty, p["reason"])
    elif action == "threshold":
        if p["target"] < p["minimum"]:
            raise Problem("Target must be at least minimum.")
        b.minimum, b.target = p["minimum"], p["target"]
    db.flush()
    event(db, actor, b.branch_id, f"inventory.{action}", b.id, p)
    return {
        "balance": dump(b),
        "available": b.on_hand - b.reserved,
        "reservation_id": reservation_id,
    }


def balances(db, actor):
    return [
        dump(b)
        | {
            "available": b.on_hand - b.reserved,
            "replenish": max(0, b.target - (b.on_hand - b.reserved))
            if b.on_hand - b.reserved < b.minimum
            else 0,
        }
        for b in db.scalars(
            select(Balance).where(
                Balance.tenant_id == actor.tenant, Balance.branch_id.in_(actor.branches)
            )
        )
    ]

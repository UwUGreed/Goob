from sqlalchemy import case, func, select

from operations.domain import agreements
from operations.domain.common import record
from operations.persistence.models import DispatchTechnician, DispatchVisit, Movement, Reservation, now


def evaluate(db, actor, job_id):
    job = record(db, actor, job_id, "jobs")
    checks = []
    for item in job.data["required_materials"]:
        reserved = db.scalar(
            select(func.coalesce(func.sum(Reservation.quantity), 0)).where(
                Reservation.tenant_id == actor.tenant,
                Reservation.job_id == job.id,
                Reservation.sku_id == item["sku_id"],
                Reservation.state == "active",
            )
        )
        outstanding = db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (Movement.kind == "issue", Movement.quantity),
                            (
                                Movement.kind.in_(["installed", "unused_return", "damaged"]),
                                -Movement.quantity,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                )
            ).where(
                Movement.tenant_id == actor.tenant,
                Movement.job_id == job.id,
                Movement.sku_id == item["sku_id"],
            )
        )
        reserved += outstanding
        checks.append(
            {
                "id": f"material:{item['sku_id']}",
                "state": "ready" if reserved >= item["quantity"] else "blocked",
                "required": item["quantity"],
                "reserved_or_issued": reserved,
            }
        )
    for identifier in job.data["prerequisites"]:
        prerequisite = record(db, actor, identifier, "jobs")
        checks.append(
            {
                "id": f"prerequisite:{identifier}",
                "state": "ready"
                if prerequisite.data.get("work_state") == "confirmed"
                else "blocked",
                "revision": prerequisite.revision,
            }
        )
    coverage = agreements.coverage(db, actor, job)
    mode = job.data["billing_mode"]
    checks.append(
        {
            "id": "coverage",
            "state": "ready"
            if mode == "nonmember" or mode == "membership" and coverage["state"] == "covered"
            else "unknown"
            if mode == "unknown" or coverage["state"] == "ambiguous"
            else "blocked",
            "evidence": coverage,
        }
    )
    checks.append(
        {
            "id": "customer_approval",
            "state": "ready" if job.data["customer_approved"] else "blocked",
        }
    )
    visit = db.scalar(
        select(DispatchVisit).where(
            DispatchVisit.tenant_id == actor.tenant,
            DispatchVisit.job_id == job.id,
        )
    )
    technician = (
        db.get(DispatchTechnician, (actor.tenant, visit.technician_id))
        if visit and visit.technician_id else None
    )
    assigned = bool(
        technician and technician.branch_id == job.branch_id
        and technician.trade == job.data["trade"]
        and visit.date and visit.start is not None and visit.end is not None
        and visit.status in {"Assigned", "En route", "Arrived", "Working", "Completed"}
    )
    checks.append(
        {
            "id": "technician_qualification_and_availability",
            "state": "ready" if assigned else "unknown",
            "reason": "Matching technician and schedule recorded in Dispatch."
            if assigned else "Assign a qualified technician and time in Dispatch.",
        }
    )
    verdict = (
        "blocked"
        if any(c["state"] == "blocked" for c in checks)
        else "unknown"
        if any(c["state"] == "unknown" for c in checks)
        else "ready"
    )
    return {
        "job_id": job.id,
        "job_revision": job.revision,
        "state": verdict,
        "checks": checks,
        "evaluated_at": now().isoformat(),
    }

from datetime import date

from sqlalchemy import select

from operations.api_v1.schemas import Extraction
from operations.domain import agreements, billing, inventory
from operations.domain.common import Problem, dump, event, get, record
from operations.persistence.models import Agreement, Benefit, Invoice, Note, Proposal, Record, uid


def validate_extraction(db, actor, job, note, extraction):
    parsed = Extraction.model_validate(extraction).model_dump(mode="json")
    if parsed["equipment_id"] is not None and parsed["equipment_id"] != job.equipment_id:
        raise Problem("Proposed equipment does not match this job.")
    for material in parsed["materials"]:
        if material["source_quote"] not in note:
            raise Problem("Material evidence is absent from the source note.")
        for field, kind in [("sku_id", "skus"), ("location_id", "locations")]:
            if material[field]:
                item = record(db, actor, material[field], kind)
                if item.branch_id != job.branch_id:
                    raise Problem("Proposed material reference is outside the job branch.")
    for followup in parsed["followups"]:
        if followup["source_quote"] not in note:
            raise Problem("Follow-up evidence is absent from the source note.")
    return parsed


def prepare(db, actor, job_id, payload, extracted=None, metadata=None):
    job = record(db, actor, job_id, "jobs", "propose", True)
    if (
        job.revision != payload["expected_job_revision"]
        or job.data.get("work_state") == "confirmed"
    ):
        raise Problem("Job changed or was already confirmed.")
    parsed = validate_extraction(
        db, actor, job, payload["note"], extracted or payload["extraction"]
    )
    note = Note(
        tenant_id=actor.tenant,
        id=uid(),
        branch_id=job.branch_id,
        job_id=job.id,
        text=payload["note"],
        actor=actor.subject,
    )
    db.add(note)
    db.flush()
    proposal = Proposal(
        tenant_id=actor.tenant,
        id=uid(),
        branch_id=job.branch_id,
        job_id=job.id,
        note_id=note.id,
        job_revision=job.revision,
        extraction=parsed,
        provider="gemini" if extracted is not None else "manual",
        provider_metadata=(metadata or {})
        | {"coverage_at_preparation": agreements.coverage(db, actor, job)},
    )
    db.add(proposal)
    db.flush()
    event(
        db,
        actor,
        job.branch_id,
        "proposal.prepared",
        proposal.id,
        {"job_id": job.id, "provider": proposal.provider},
    )
    return dump(proposal)


def review(db, actor, identifier, payload):
    p = get(
        db,
        actor,
        Proposal,
        identifier,
        "approve" if payload["action"] == "approve" else "propose",
        True,
    )
    job = record(db, actor, p.job_id, "jobs", lock=True)
    if p.revision != payload["expected_revision"]:
        raise Problem("Proposal revision changed.")
    if p.state != "pending":
        raise Problem("Proposal has already been reviewed.")
    if job.revision != p.job_revision:
        raise Problem("Job changed; prepare a fresh proposal.")
    before = dump(p)
    if payload["action"] == "reject":
        p.state = "rejected"
    elif payload["action"] == "revise":
        if not payload.get("extraction"):
            raise Problem("Revised extraction required.", 422)
        note = get(db, actor, Note, p.note_id)
        extraction = validate_extraction(db, actor, job, note.text, payload["extraction"])
        p.state = "superseded"
        replacement = Proposal(
            tenant_id=actor.tenant,
            id=uid(),
            branch_id=p.branch_id,
            job_id=p.job_id,
            note_id=p.note_id,
            job_revision=job.revision,
            extraction=extraction,
            parent_id=p.id,
            provider="human_revision",
            provider_metadata={"coverage_at_preparation": agreements.coverage(db, actor, job)},
        )
        db.add(replacement)
        db.flush()
        event(
            db,
            actor,
            p.branch_id,
            "proposal.revised",
            replacement.id,
            {"previous_id": p.id, "reason": payload["reason"]},
        )
        return dump(replacement)
    else:
        e = p.extraction
        if (
            not e["completed"]
            or e["unknowns"]
            or e["equipment_id"] != job.equipment_id
            or any(not m["sku_id"] or not m["location_id"] for m in e["materials"])
        ):
            raise Problem(
                "Resolve incomplete work and unknown equipment/materials before approval."
            )
        coverage = agreements.coverage(db, actor, job)
        if coverage != p.provider_metadata["coverage_at_preparation"]:
            raise Problem("Coverage changed; prepare or revise the proposal.")
        mode = job.data["billing_mode"]
        if mode == "unknown" or not job.data["customer_approved"]:
            raise Problem("Customer approval and a reviewed billing mode are required.")
        if mode == "membership" and coverage["state"] != "covered":
            raise Problem("Membership does not cover this completed service.")
        snapshot = billing.review(job, coverage, e["materials"], payload["dismissed_findings"])
        if snapshot["unresolved"]:
            raise Problem("Resolve missing draft material lines or dismiss each with a reason.")
        for material in e["materials"]:
            inventory.dispose(db, actor, job, material)
        from operations.persistence.models import Movement

        pairs = db.execute(
            select(Movement.sku_id, Movement.location_id)
            .where(Movement.tenant_id == actor.tenant, Movement.job_id == job.id)
            .distinct()
        ).all()
        if any(inventory.outstanding(db, actor, job.id, sku, location) for sku, location in pairs):
            raise Problem("Record disposition of every issued part before confirming work.")
        if mode == "membership" and coverage.get("portal_membership"):
            from operations.domain import service_memberships
            service_memberships.reconcile(db,actor,job,True,f"Confirmed proposal {p.id}")
        elif mode == "membership" and job.data["service"]=="maintenance":
            db.add(
                Benefit(
                    tenant_id=actor.tenant,
                    branch_id=job.branch_id,
                    agreement_id=coverage["agreement_id"],
                    job_id=job.id,
                    amount=-1,
                    effective_on=date.fromisoformat(job.data["service_date"]),
                    reason=f"Confirmed proposal {p.id}",
                )
            )
        invoice = Invoice(
            tenant_id=actor.tenant,
            id=uid(),
            branch_id=job.branch_id,
            job_id=job.id,
            proposal_id=p.id,
            snapshot=snapshot,
        )
        db.add(invoice)
        p.state = "approved"
        job.data = job.data | {"work_state": "confirmed", "completed_work": e["completed_work"]}
        job.revision += 1
        for followup in e["followups"]:
            db.add(
                Record(
                    tenant_id=actor.tenant,
                    branch_id=job.branch_id,
                    kind="opportunities",
                    name=followup["description"][:250],
                    customer_id=job.customer_id,
                    property_id=job.property_id,
                    data=followup
                    | {"source_job_id": job.id, "source_note_id": p.note_id, "state": "reviewed"},
                )
            )
        event(
            db,
            actor,
            p.branch_id,
            "work.confirmed",
            job.id,
            {
                "proposal_id": p.id,
                "equipment_id": job.equipment_id,
                "invoice": snapshot,
                "reason": payload["reason"],
            },
        )
    p.revision += 1
    db.flush()
    event(
        db,
        actor,
        p.branch_id,
        f"proposal.{p.state}",
        p.id,
        {"before": before, "after": dump(p), "reason": payload["reason"]},
    )
    return dump(p)


def reverse(db, actor, job_id, reason):
    job = record(db, actor, job_id, "jobs", "approve", True)
    if job.data.get("work_state") != "confirmed":
        raise Problem("Only confirmed work can be reversed.")
    last = db.scalar(
        select(Proposal)
        .where(
            Proposal.tenant_id == actor.tenant,
            Proposal.job_id == job.id,
            Proposal.state == "approved",
        )
        .with_for_update()
    )
    if not last:
        raise Problem("Approval evidence is missing.")
    entries = db.scalars(
        select(Benefit).where(
            Benefit.tenant_id == actor.tenant,
            Benefit.job_id == job.id,
            Benefit.reason == f"Confirmed proposal {last.id}",
        )
    ).all()
    for entry in entries:
        db.add(
            Benefit(
                tenant_id=actor.tenant,
                branch_id=job.branch_id,
                agreement_id=entry.agreement_id,
                job_id=job.id,
                amount=-entry.amount,
                effective_on=entry.effective_on,
                reason=f"Reversal of {entry.id}: {reason}",
            )
        )
    from operations.domain import service_memberships
    if any(a.portal_meta.get("planId") for a in db.scalars(select(Agreement).where(Agreement.tenant_id==actor.tenant,Agreement.equipment_id==job.equipment_id))):
        service_memberships.reconcile(db,actor,job,False,reason)
    last.state = "reversed"
    last.revision += 1
    job.data = job.data | {"work_state": "reopened"}
    job.revision += 1
    event(
        db,
        actor,
        job.branch_id,
        "work.reversed",
        job.id,
        {
            "proposal_id": last.id,
            "reason": reason,
            "inventory_effect": "none",
            "invoice_effect": "original preserved; superseding draft required",
        },
    )
    db.flush()
    return dump(job)

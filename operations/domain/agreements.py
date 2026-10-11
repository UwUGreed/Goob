from datetime import date

from sqlalchemy import func, select

from operations.domain.common import Problem, dump, event, get, record
from operations.persistence.models import Agreement, Benefit, Terms, now, uid


def balance(db, tenant, identifier, day=None):
    agreement = db.get(Agreement, (tenant, identifier))
    if agreement and agreement.portal_meta.get("configuration"):
        from operations.domain import service_memberships
        effective = day or now().date()
        terms = service_memberships.current_terms(db, agreement, effective)
        return service_memberships.remaining(db, agreement, terms, effective) if terms else 0
    return db.scalar(
        select(func.coalesce(func.sum(Benefit.amount), 0)).where(
            Benefit.tenant_id == tenant,
            Benefit.agreement_id == identifier,
            (Benefit.effective_on <= (day or now().date())) | (Benefit.amount < 0),
        )
    )


def add_terms(db, actor, agreement, values):
    terms = Terms(
        tenant_id=actor.tenant,
        id=uid(),
        branch_id=agreement.branch_id,
        agreement_id=agreement.id,
        **{k: v for k, v in values.items() if k != "grant"},
    )
    terms.due_dates = [str(d) for d in terms.due_dates]
    db.add(terms)
    db.flush()
    db.add(
        Benefit(
            tenant_id=actor.tenant,
            branch_id=agreement.branch_id,
            agreement_id=agreement.id,
            amount=values["grant"],
            effective_on=values["starts"],
            reason=f"Term grant {terms.id}",
        )
    )
    return terms


def create(db, actor, values):
    unit = record(db, actor, values["equipment_id"], "equipment", "write")
    if unit.data["trade"] != values["trade"]:
        raise Problem("Agreement trade must match equipment.")
    agreement = Agreement(
        tenant_id=actor.tenant,
        id=uid(),
        branch_id=unit.branch_id,
        **{k: v for k, v in values.items() if k != "terms"},
    )
    db.add(agreement)
    db.flush()
    terms = add_terms(db, actor, agreement, values["terms"])
    event(db, actor, unit.branch_id, "agreement.created", agreement.id, {"terms": dump(terms)})
    return {"agreement": dump(agreement), "terms": dump(terms)}


def coverage(db, actor, job):
    # Portal plans use explicit per-charge rules and maintenance-only allowances.
    portal = db.scalar(select(Agreement).where(Agreement.tenant_id==actor.tenant,Agreement.equipment_id==job.equipment_id,Agreement.portal_meta["planId"].astext.is_not(None)))
    if portal:
        from operations.domain import service_memberships
        result=service_memberships.eligibility(db,actor,job)
        if not result["eligible"]:
            return {"state":"uncovered","matches":0}
        a=get(db,actor,Agreement,result["membershipId"])
        t=service_memberships.current_terms(db,a,date.fromisoformat(job.data["service_date"]))
        consumed=db.scalar(select(func.coalesce(func.sum(Benefit.amount),0)).where(Benefit.tenant_id==actor.tenant,Benefit.agreement_id==a.id,Benefit.job_id==job.id))<0
        return {"state":"covered" if job.data["service"]!="maintenance" or result["remaining"]>0 or consumed else "exhausted","agreement_id":a.id,"agreement_revision":a.revision,"terms_id":t.id,"discount":0,"discountRules":result["discountRules"],"remaining":result["remaining"],"terms":t.description,"portal_membership":True}
    day = date.fromisoformat(job.data["service_date"])
    pairs = db.execute(
        select(Agreement, Terms)
        .join(
            Terms, (Terms.tenant_id == Agreement.tenant_id) & (Terms.agreement_id == Agreement.id)
        )
        .where(
            Agreement.tenant_id == actor.tenant,
            Agreement.equipment_id == job.equipment_id,
            Agreement.trade == job.data["trade"],
            Agreement.service == job.data["service"],
            Agreement.status != "pending",
            Terms.starts <= day,
            (Agreement.canceled_on.is_(None)) | (Agreement.canceled_on > day),
        )
    ).all()
    # Immutable term versions may overlap; latest effective version wins within
    # an agreement, while overlapping independent agreements remain ambiguous.
    latest = {}
    for agreement, terms in pairs:
        if agreement.id not in latest or terms.starts > latest[agreement.id][1].starts:
            latest[agreement.id] = (agreement, terms)
    pairs = [(agreement, terms) for agreement, terms in latest.values() if terms.ends >= day]
    if len(pairs) != 1:
        return {"state": "uncovered" if not pairs else "ambiguous", "matches": len(pairs)}
    agreement, terms = pairs[0]
    remaining = balance(db, actor.tenant, agreement.id, day)
    return {
        "state": "covered" if remaining > 0 else "exhausted",
        "agreement_id": agreement.id,
        "agreement_revision": agreement.revision,
        "terms_id": terms.id,
        "discount": terms.discount,
        "remaining": remaining,
        "terms": terms.description,
    }


def change(db, actor, identifier, payload):
    agreement = get(db, actor, Agreement, identifier, "write", True)
    if agreement.revision != payload["expected_revision"]:
        raise Problem("Agreement revision changed.")
    action = payload["action"]
    before = dump(agreement)
    if action in {"preview", "renew", "upgrade"}:
        terms = payload.get("terms")
        if not terms:
            raise Problem("Terms required.", 422)
        versions = db.scalars(
            select(Terms)
            .where(Terms.tenant_id == actor.tenant, Terms.agreement_id == identifier)
            .order_by(Terms.starts)
        ).all()
        if action == "preview":
            return {
                "current": [dump(t) for t in versions],
                "proposed": {k: str(v) if isinstance(v, date) else v for k, v in terms.items()},
                "remaining": balance(db, actor.tenant, identifier),
                "financial_effect": "No automatic charge, refund, or proration.",
            }
        if agreement.canceled_on or terms["starts"] <= versions[-1].starts:
            raise Problem("New terms must follow the latest version on an uncanceled agreement.")
        if action == "renew" and terms["starts"] <= versions[-1].ends:
            raise Problem("Renewal must start after the current term.")
        if action == "upgrade":
            if terms["starts"] < now().date():
                raise Problem("Retroactive upgrades require manual historical reconciliation.")
            # Keep the original terms immutable. Coverage selects effective versions.
        add_terms(db, actor, agreement, terms)
    elif action == "cancel":
        effective = payload.get("effective_date")
        if not effective or effective < now().date():
            raise Problem("Cancellation requires a present or future effective date.")
        agreement.canceled_on = effective
        agreement.status = "canceled" if effective <= now().date() else "cancellation_scheduled"
    elif action == "adjust":
        if balance(db, actor.tenant, identifier) + payload["amount"] < 0:
            raise Problem("Adjustment would create a negative benefit balance.")
        db.add(
            Benefit(
                tenant_id=actor.tenant,
                branch_id=agreement.branch_id,
                agreement_id=identifier,
                amount=payload["amount"],
                reason=payload["reason"],
            )
        )
    agreement.revision += 1
    event(
        db,
        actor,
        agreement.branch_id,
        f"agreement.{action}",
        identifier,
        {"before": before, "after": dump(agreement), "reason": payload["reason"]},
    )
    db.flush()
    return {"agreement": dump(agreement), "remaining": balance(db, actor.tenant, identifier)}


def obligations(db, actor, day):
    result = []
    for agreement in db.scalars(
        select(Agreement).where(
            Agreement.tenant_id == actor.tenant, Agreement.branch_id.in_(actor.branches)
        )
    ):
        versions = db.scalars(
            select(Terms)
            .where(Terms.tenant_id == actor.tenant, Terms.agreement_id == agreement.id)
            .order_by(Terms.starts.desc())
        ).all()
        current = next((t for t in versions if t.starts <= day), None)
        if not current:
            continue
        completed = -db.scalar(
            select(func.coalesce(func.sum(Benefit.amount), 0)).where(
                Benefit.tenant_id == actor.tenant,
                Benefit.agreement_id == agreement.id,
                Benefit.job_id.is_not(None),
                Benefit.effective_on >= current.starts,
                Benefit.effective_on <= day,
            )
        )
        scheduled_due = sorted(d for d in current.due_dates if d <= day.isoformat())
        due = scheduled_due[max(0, completed) :]
        state = (
            "canceled"
            if agreement.canceled_on and agreement.canceled_on <= day
            else "expired"
            if current.ends < day
            else "active"
        )
        result.append(
            {
                "agreement_id": agreement.id,
                "equipment_id": agreement.equipment_id,
                "trade": agreement.trade,
                "state": state,
                "remaining": balance(db, actor.tenant, agreement.id, day),
                "scheduled_service_due": due if state == "active" else [],
                "renewal_date": current.ends.isoformat(),
                "days_to_term_end": (current.ends - day).days,
                "schedule_defined": bool(current.due_dates),
            }
        )
    return result

"""Portal service memberships reuse immutable terms and the audited benefit ledger.
Each enrollment covers one explicitly selected equipment unit. Plans are reusable;
enrollment snapshots prevent later plan edits from silently changing old terms.
"""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select, func
from operations.domain import agreements
from operations.domain.common import Problem, event, get, module, record
from operations.persistence.models import Agreement, Benefit, ServicePlan, Terms, now


def integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise Problem(f"Enter a valid {label} ({low}–{high}).", 422)
    return value


def configuration(p):
    trades = p.get("trades")
    if not isinstance(trades, list) or not trades or any(t not in {"HVAC", "Electrical", "Plumbing"} for t in trades):
        raise Problem("Choose covered trades.", 422)
    rules = p.get("discountRules", [])
    if not isinstance(rules, list) or len(rules) > 10:
        raise Problem("Invalid discount rules.", 422)
    cleaned = []
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("kind") not in {"labor", "material", "other"} or rule.get("service") not in {"repair", "maintenance"}:
            raise Problem("Discount rules require a charge kind and eligible service.", 422)
        cleaned.append({"kind": rule["kind"], "service": rule["service"], "percent": integer(rule.get("percent"), 0, 100, "discount")})
    if len({(r["kind"], r["service"]) for r in cleaned}) != len(cleaned):
        raise Problem("Only one discount rule per charge kind and service.", 422)
    return {"trades": sorted(set(trades)), "termDays": integer(p.get("termDays"), 1, 3660, "term days"), "visits": integer(p.get("visits"), 0, 100, "included visits"), "discountRules": cleaned}


def current_terms(db, a, day=None):
    versions = db.scalars(select(Terms).where(Terms.tenant_id == a.tenant_id, Terms.agreement_id == a.id).order_by(Terms.starts.desc())).all()
    return next((t for t in versions if t.starts <= (day or now().date())), versions[-1] if versions else None)


def remaining(db, a, t, day):
    if not a.portal_meta.get("configuration"):
        return agreements.balance(db,a.tenant_id,a.id,day)
    # Immutable per-term allowance; future renewal grants never affect today's balance.
    net = db.scalar(select(func.coalesce(func.sum(Benefit.amount),0)).where(Benefit.tenant_id==a.tenant_id,Benefit.agreement_id==a.id,Benefit.reason.not_like("Term grant %"),Benefit.effective_on>=t.starts,Benefit.effective_on<=min(day,t.ends)))
    grant = db.scalar(select(func.coalesce(func.sum(Benefit.amount),0)).where(Benefit.tenant_id==a.tenant_id,Benefit.agreement_id==a.id,Benefit.reason==f"Term grant {t.id}"))
    return max(0,grant+net)


def state(a, t, day):
    if a.canceled_on and a.canceled_on <= day:
        return "canceled"
    if a.status == "pending" or not t or t.starts > day:
        return "pending"
    return "expired" if t.ends < day else "active"


def eligibility(db, actor, job):
    day = date.fromisoformat(job.data["service_date"])
    candidates = db.scalars(select(Agreement).where(Agreement.tenant_id == actor.tenant, Agreement.equipment_id == job.equipment_id, Agreement.trade == job.data["trade"], Agreement.branch_id == job.branch_id)).all()
    matches = []
    for a in candidates:
        t = current_terms(db, a, day)
        if state(a, t, day) == "active" and (a.portal_meta.get("configuration") or a.service == job.data["service"]):
            matches.append((a, t))
    if len(matches) != 1:
        return {"eligible": False, "reason": "Overlapping coverage requires review." if matches else "No active coverage for this equipment, trade and service date.", "remaining": 0, "discountRules": []}
    a, t = matches[0]
    # Verify actual property/customer hierarchy rather than trusting customer-level enrollment.
    unit = record(db, actor, a.equipment_id, "equipment")
    site = record(db, actor, unit.parent_id, "properties")
    if site.id != job.property_id or site.parent_id != job.customer_id:
        return {"eligible": False, "reason": "Property or customer differs from the enrolled equipment.", "remaining": 0, "discountRules": []}
    left = remaining(db,a,t,day)
    rules = a.portal_meta.get("configuration", {}).get("discountRules", [])
    return {"eligible": True, "membershipId": a.id, "reason": f"Covered equipment · {a.trade} · within term. Repairs do not use maintenance visits.", "remaining": left, "maintenanceEligible": job.data["service"] == "maintenance" and left > 0, "discountRules": rules}


def charge_proposal(lines, rules, service):
    proposed = []
    for line in lines:
        gross = line["unit_cents"] * line["quantity"]
        percent = next((r["percent"] for r in rules if r["kind"] == line["kind"] and r["service"] == service), 0) if line.get("discount_eligible") and line.get("treatment", "billable") == "billable" else 0
        discount = int((Decimal(gross) * Decimal(percent) / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        total = gross-discount if line.get("treatment", "billable") == "billable" else 0
        proposed.append({"description": line["description"], "kind": line["kind"], "grossCents": gross, "discountPercent": percent, "discountCents": discount, "totalCents": total})
    return {"lines": proposed, "totalCents": sum(l["totalCents"] for l in proposed)}


def reconcile(db, actor, job, completed, reason):
    """Net ledger usage is authoritative. Recompletion and correction are idempotent."""
    module(db, actor, "agreements")
    usage = db.execute(select(Benefit.agreement_id, func.sum(Benefit.amount)).where(Benefit.tenant_id == actor.tenant, Benefit.job_id == job.id).group_by(Benefit.agreement_id)).all()
    coverage = eligibility(db, actor, job) if completed else {"eligible": False}
    # Previously consumed benefits remain valid on a repeated completion, even if exhausted.
    desired = coverage.get("membershipId") if completed and job.data["service"] == "maintenance" and coverage.get("eligible") else None
    for aid, net in usage:
        if net < 0 and aid != desired:
            a = get(db, actor, Agreement, aid, "write", True)
            db.add(Benefit(tenant_id=actor.tenant, branch_id=a.branch_id, agreement_id=aid, job_id=job.id, amount=-net, effective_on=date.fromisoformat(job.data["service_date"]), reason=reason))
            event(db, actor, job.branch_id, "membership.usage.reversed", job.id, {"membership_id": aid, "amount": -net, "reason": reason})
    net = dict(usage).get(desired, 0)
    if desired and net == 0:
        a = get(db, actor, Agreement, desired, "write", True)
        day = date.fromisoformat(job.data["service_date"])
        if remaining(db,a,current_terms(db,a,day),day) <= 0:
            raise Problem("Maintenance allowance exhausted. Review before completing this visit.")
        db.add(Benefit(tenant_id=actor.tenant, branch_id=a.branch_id, agreement_id=a.id, job_id=job.id, amount=-1, effective_on=date.fromisoformat(job.data["service_date"]), reason=reason))
        event(db, actor, job.branch_id, "membership.usage.consumed", job.id, {"membership_id": a.id, "amount": -1, "reason": reason})
    db.flush()


def snapshot(db, actor, rows):
    catalog = {r.id: r for r in rows}
    plans = [{"id": p.id, "name": p.name, "revision": p.revision, **p.configuration} for p in db.scalars(select(ServicePlan).where(ServicePlan.tenant_id == actor.tenant, ServicePlan.branch_id.in_(actor.branches)))]
    result = []
    for a in db.scalars(select(Agreement).where(Agreement.tenant_id == actor.tenant, Agreement.branch_id.in_(actor.branches))):
        unit = catalog.get(a.equipment_id)
        site = catalog.get(unit.parent_id) if unit else None
        customer = catalog.get(site.parent_id) if site else None
        t = current_terms(db, a)
        if not t:
            continue
        history = [{"id": b.id, "jobId": b.job_id, "amount": b.amount, "reason": b.reason, "date": b.effective_on.isoformat()} for b in db.scalars(select(Benefit).where(Benefit.tenant_id == actor.tenant, Benefit.agreement_id == a.id).order_by(Benefit.created_at.desc()))]
        left = remaining(db,a,t,now().date())
        used = -sum(b["amount"] for b in history if b["jobId"] and b["date"] >= t.starts.isoformat())
        due = sorted(d for d in t.due_dates if d <= now().date().isoformat())[max(0,used):]
        result.append({"id": a.id, "revision": a.revision, "customerId": customer.id if customer else "", "customer": customer.name if customer else "Unavailable customer", "propertyId": site.id if site else "", "property": site.name if site else "Unavailable property", "equipmentId": a.equipment_id, "equipment": unit.name if unit else "Unavailable equipment", "trade": a.trade, "planId": a.portal_meta.get("planId", ""), "plan": a.portal_meta.get("planName", t.description), "status": state(a,t,now().date()), "paymentStatus": a.portal_meta.get("paymentStatus", "unrecorded"), "starts": t.starts.isoformat(), "ends": t.ends.isoformat(), "remaining": left, "due": due, "renewalSoon": 0 <= (t.ends-now().date()).days <= 30, "configuration": a.portal_meta.get("configuration", {}), "history": history})
    return plans, result


def run(db, actor, action):
    module(db, actor, "agreements")
    kind = action["operation"]
    p = action.get("values", {})
    if kind == "plan":
        config = configuration(p)
        name = p.get("name", "").strip()
        if not name or len(name)>100:
            raise Problem("Enter a plan name.",422)
        plan = get(db, actor, ServicePlan, p["id"], "write", True) if p.get("id") else ServicePlan(tenant_id=actor.tenant, branch_id=actor.branches[0], name=name, configuration=config)
        actor.allow(plan.branch_id, "write")
        if p.get("id"):
            if p.get("revision") != plan.revision:
                raise Problem("Plan changed. Reload before editing.")
            plan.name, plan.configuration, plan.revision = name, config, plan.revision+1
        db.add(plan);db.flush()
        event(db, actor, plan.branch_id, "membership.plan.saved", plan.id, config)
        return
    if kind == "enroll":
        plan = get(db, actor, ServicePlan, p.get("planId"))
        unit = record(db, actor, p.get("equipmentId"), "equipment", "write")
        site = record(db, actor, unit.parent_id, "properties")
        if plan.branch_id != unit.branch_id or unit.data["trade"] not in plan.configuration["trades"] or site.parent_id != p.get("customerId") or site.id != p.get("propertyId"):
            raise Problem("Select matching customer, property and covered equipment.",422)
        try:
            start = date.fromisoformat(p.get("starts", ""))
        except (ValueError, TypeError):
            raise Problem("Choose a valid start date.",422) from None
        end = start + timedelta(days=plan.configuration["termDays"]-1)
        overlaps = db.scalars(select(Agreement).where(Agreement.tenant_id==actor.tenant, Agreement.equipment_id==unit.id, Agreement.canceled_on.is_(None))).all()
        for a in overlaps:
            terms = current_terms(db,a,start)
            if terms and terms.starts <= end and terms.ends >= start:
                raise Problem("Equipment already has overlapping membership coverage.")
        result = agreements.create(db,actor,{"equipment_id":unit.id,"trade":unit.data["trade"],"service":"maintenance","terms":{"starts":start,"ends":end,"discount":0,"description":plan.name,"grant":plan.configuration["visits"],"due_dates":[(start+timedelta(days=i*plan.configuration["termDays"]//plan.configuration["visits"])).isoformat() for i in range(plan.configuration["visits"])]}})
        a = get(db,actor,Agreement,result["agreement"]["id"],"write",True)
        a.portal_meta = {"planId":plan.id,"planName":plan.name,"configuration":plan.configuration,"paymentStatus":"unpaid"}
        a.status = "pending" if p.get("status")=="pending" else "active"
        return
    a = get(db,actor,Agreement,p.get("id"),"write",True)
    if p.get("revision") != a.revision:
        raise Problem("Membership changed. Reload before editing.")
    if kind == "edit":
        if p.get("paymentStatus") not in {"paid","unpaid","overdue","unrecorded"} or p.get("status") not in {"active","pending"} or a.canceled_on:
            raise Problem("Choose valid membership and payment statuses. Canceled terms cannot reactivate.",422)
        a.status = p["status"]
        a.portal_meta = a.portal_meta | {"paymentStatus":p["paymentStatus"]}
        a.revision += 1
        event(db,actor,a.branch_id,"membership.edited",a.id,p)
    elif kind == "cancel":
        agreements.change(db,actor,a.id,{"action":"cancel","expected_revision":a.revision,"effective_date":now().date(),"reason":"Manual membership cancellation; historical visits retained"})
    elif kind == "renew":
        t = db.scalar(select(Terms).where(Terms.tenant_id==actor.tenant, Terms.agreement_id==a.id).order_by(Terms.starts.desc()))
        start = max(t.ends+timedelta(days=1),now().date())
        config = a.portal_meta.get("configuration")
        if not config:
            raise Problem("Legacy agreement needs reviewed terms through Work review.")
        agreements.change(db,actor,a.id,{"action":"renew","expected_revision":a.revision,"terms":{"starts":start,"ends":start+timedelta(days=config["termDays"]-1),"discount":0,"description":a.portal_meta["planName"],"grant":config["visits"],"due_dates":[(start+timedelta(days=i*config["termDays"]//config["visits"])).isoformat() for i in range(config["visits"])]},"reason":"Manual renewal; no automatic payment"})
    else:
        raise Problem("Unsupported membership operation.",422)

"""Portal adapters over the scoped CRM, inventory and dispatch ORM records."""
from datetime import datetime, timezone
from sqlalchemy import select, func
from operations.domain import crm, inventory, service_memberships
from operations.domain.common import Problem, event, module, record
from operations.persistence.models import Balance, DispatchTechnician, DispatchVisit, Record, Reservation, Movement, Event, Tenant, uid

NODES = {f"{x}-{z}" for x in range(4) for z in range(4)}
TRADES = {"Plumbing", "HVAC", "Electrical"}
STATUSES = {"Unassigned", "Assigned", "En route", "Arrived", "Working", "Completed"}


def scoped(db, actor, model):
    return db.scalars(select(model).where(model.tenant_id == actor.tenant, model.branch_id.in_(actor.branches))).all()


def snapshot(db, actor):
    module(db, actor, "jobs")
    module(db, actor, "inventory")
    rows = [r for r in scoped(db, actor, Record) if not r.archived]
    catalog = {r.id: r for r in rows}
    visits = {v.job_id: v for v in scoped(db, actor, DispatchVisit)}
    techs = scoped(db, actor, DispatchTechnician)
    def name(identifier):
        return catalog[identifier].name if identifier in catalog else "Not recorded"
    membership_enabled = "agreements" in db.get(Tenant,actor.tenant).modules
    plans, memberships = service_memberships.snapshot(db, actor, rows) if membership_enabled else ([],[])
    properties = [{"id":r.id,"customerId":r.parent_id,"name":r.name,"address":r.data.get("address", ""),"revision":r.revision} for r in rows if r.kind=="properties"]
    equipment = [{"id":r.id,"propertyId":r.parent_id,"name":r.name,**r.data} for r in rows if r.kind=="equipment"]
    events = sorted(scoped(db,actor,Event),key=lambda e:e.created_at)
    customers = []
    for c in rows:
        if c.kind == "customers":
            sites = [r for r in rows if r.kind == "properties" and r.parent_id == c.id]
            primary = next((s for s in sites if s.id == c.data.get("primary_property_id")), sites[0] if sites else None)
            customers.append({"id": c.id, "name": c.name, "email": c.data.get("email", ""), "phone": c.data.get("phone", ""), "address": primary.data["address"] if primary else "", "addresses": [s.data["address"] for s in sites], "branchId": c.branch_id, "verification":c.portal_meta.get("verification",False), "accountType":c.data.get("account_type", "residential"), "contacts":[{"name":r.name,**r.data} for r in rows if r.kind=="contacts" and r.parent_id==c.id]})
    jobs, statuses, bookings = [], {}, {}
    ordered_jobs = sorted((r for r in scoped(db,actor,Record) if r.kind == "jobs"), key=lambda r:(r.created_at, r.id))
    numbers = {j.id: str(2001+n) for n,j in enumerate(ordered_jobs)}
    for j in rows:
        if j.kind != "jobs":
            continue
        v = visits.get(j.id)
        needs = [{"skuId": n["sku_id"], "part": name(n["sku_id"]), "quantity": n["quantity"]} for n in j.data.get("required_materials", [])]
        site = catalog.get(j.property_id)
        coverage = service_memberships.eligibility(db,actor,j) if membership_enabled else {"eligible":False,"reason":"Membership module unavailable.","remaining":0,"discountRules":[]}
        proposal = service_memberships.charge_proposal(j.data.get("lines",[]),coverage.get("discountRules",[]),j.data["service"])
        jobs.append({"id": j.id, "customerId": j.customer_id, "customer": name(j.customer_id), "title": j.name, "address": site.data["address"] if site else "Not recorded", "trade": j.data["trade"], "description": v.description if v else "", "part": needs[0]["part"] if needs else "No parts required", "requirements": needs, "node": v.node if v else "unknown", "urgent": v.urgent if v else False, "time": v.requested if v else j.data["service_date"], "branchId": j.branch_id, "displayNumber":j.portal_meta.get("displayNumber",numbers[j.id]), "verification":j.portal_meta.get("verification",False), "propertyId":j.property_id,"equipmentId":j.equipment_id,"service":j.data["service"],"serviceDate":j.data["service_date"],"lines":j.data.get("lines",[]),"coverage":coverage,"chargeProposal":proposal,"appliedCharge":j.portal_meta.get("appliedCharge"),"notes":j.portal_meta.get("notes", ""),"reviewed":(j.portal_meta.get("reviewed",False) and j.portal_meta.get("appliedCharge")==proposal) or j.data.get("work_state")=="confirmed","history":[{"kind":e.kind,"date":e.created_at.isoformat(),"actor":"Office" if e.actor.startswith("portal-demo-") else e.actor} for e in events if e.resource_id==j.id or e.evidence.get("job_id")==j.id]})
        statuses[j.id] = v.status if v else "Completed" if j.data.get("work_state") == "confirmed" else "Unassigned"
        if v and v.technician_id and v.start is not None:
            bookings[j.id] = {"techId": v.technician_id, "date": v.date, "start": v.start, "end": v.end, "travelStart": v.travel_start}
    colors = {"Plumbing": "#3485db", "HVAC": "#319b72", "Electrical": "#e1a43d"}
    roster = [{"id": t.id, "name": t.name, "trade": t.trade, "truck": name(t.location_id), "branchId": t.branch_id, "locationId": t.location_id, "initials": "".join(p[0] for p in t.name.split())[:2], "color": colors[t.trade], "start": t.node} for t in techs]
    stock = [{"id": b.id, "skuId": b.sku_id, "locationId": b.location_id, "part": name(b.sku_id), "sku": catalog[b.sku_id].data.get("barcode") or "SKU not recorded", "trade": catalog[b.sku_id].data.get("trade", "Plumbing"), "truck": "Warehouse" if catalog[b.location_id].data["location_type"] == "warehouse" else name(b.location_id), "quantity": b.on_hand, "reservedQuantity":b.reserved, "threshold": b.minimum, "branchId": b.branch_id, "skuRevision": catalog[b.sku_id].revision, **{k:catalog[b.sku_id].data.get(k) for k in ("image_url","image_alt","image_attribution","image_source","image_illustrative")}} for b in scoped(db, actor, Balance)]
    reservations = [{"id":r.id,"jobId": r.job_id, "part": name(r.sku_id), "truck": name(r.location_id), "quantity": r.quantity} for r in scoped(db, actor, Reservation) if r.state == "active"]
    movements = [{"id":m.id,"part":name(m.sku_id),"location":name(m.location_id),"locationId":m.location_id,"jobId":m.job_id,"kind":m.kind,"quantity":m.quantity,"delta":m.delta,"reason":m.reason,"date":m.created_at.isoformat()} for m in sorted(scoped(db,actor,Movement),key=lambda m:m.created_at,reverse=True)]
    locations = [{"id":r.id,"name":r.name,"type":r.data["location_type"]} for r in rows if r.kind=="locations"]
    return {"properties":properties,"equipment":equipment,"plans":plans,"memberships":memberships,"movements":movements,"locations":locations,"databaseBacked": True, "roster": roster, "records": jobs, "customers": customers, "stock": stock, "reservations": reservations, "bookings": bookings, "jobs": statuses, "speed": 1, "technicians": {t.id: {"status": t.status, "node": t.node, "jobId": t.job_id, "route": [], "progress": 0, "running": False, "duration": 0} for t in techs}}


def text(value, field, maximum=500, optional=False):
    result = value.get(field)
    if not isinstance(result, str) or len(result) > maximum or (not optional and not result.strip()):
        raise Problem(f"Enter a valid {field}.", 422)
    return result.strip()


def create(db, actor, kind, branch, name, data, identifier=None, **links):
    value = crm.create(db, actor, kind, {"branch_id": branch, "name": name, "data": data, **links}, identifier=identifier)
    return record(db, actor, value["id"], kind)


def location_for(db, actor, branch, name):
    if name == "Warehouse":
        location = db.scalar(select(Record).where(Record.tenant_id == actor.tenant, Record.branch_id == branch, Record.kind == "locations", Record.data["location_type"].astext == "warehouse", Record.archived.is_(False)))
    else:
        location = db.scalar(select(Record).where(Record.tenant_id == actor.tenant, Record.branch_id == branch, Record.kind == "locations", Record.name == name, Record.archived.is_(False)))
    if not location:
        raise Problem("Select a recorded stock location.", 422)
    return location


def run(db, actor, action):
    module(db, actor, "jobs")
    module(db, actor, "inventory")
    if not actor.branches:
        raise Problem("No workspace branch access.", 403)
    branch = actor.branches[0]
    kind = action.get("type")
    if kind == "membership":
        service_memberships.run(db, actor, action)
    elif kind == "property":
        p = action.get("values", {})
        c = record(db,actor,p.get("customerId"),"customers","write")
        if p.get("id"):
            row = record(db,actor,p["id"],"properties","write",True)
            if row.parent_id != c.id or row.revision != p.get("revision"):
                raise Problem("Property changed or does not belong to this customer.")
            crm.patch(db,actor,"properties",row.id,{"expected_revision":row.revision,"name":text(p,"name",100),"data":{"address":text(p,"address",200)}})
        else:
            create(db,actor,"properties",c.branch_id,text(p,"name",100),{"address":text(p,"address",200)},parent_id=c.id)
    elif kind == "image":
        p=action.get("values",{})
        sku=record(db,actor,p.get("sku_id"),"skus","write",True)
        if p.get("expected_revision") != sku.revision:
            raise Problem("Item changed. Refresh before replacing its image.")
        fields={k:p.get(k, "" if k!="image_illustrative" else True) for k in ("image_url","image_alt","image_attribution","image_source","image_illustrative")}
        if fields["image_url"] and (not isinstance(fields["image_alt"],str) or not fields["image_alt"].strip()):
            raise Problem("Describe the image for accessibility.",422)
        crm.patch(db,actor,"skus",sku.id,{"expected_revision":sku.revision,"data":sku.data|fields})
    elif kind == "movement":
        from operations.api_v1.schemas import InventoryCommand
        from pydantic import ValidationError
        try:
            values = InventoryCommand.model_validate(action.get("values",{})).model_dump(mode="json")
        except ValidationError as exc:
            raise Problem(str(exc),422) from exc
        if values["action"] not in {"receive","transfer","return","adjust","issue"}:
            raise Problem("Unsupported stock movement.",422)
        if values["action"] == "issue":
            job = record(db,actor,values.get("job_id"),"jobs","write",True)
            visit = db.scalar(select(DispatchVisit).where(DispatchVisit.tenant_id==actor.tenant,DispatchVisit.job_id==job.id))
            if visit and visit.status == "Completed":
                raise Problem("Completed jobs cannot consume additional stock.")
        inventory.execute(db,actor,values)
    elif kind == "job-review":
        p = action.get("values",{})
        job = record(db,actor,p.get("id"),"jobs","write",True)
        operation = p.get("operation")
        if operation == "notes":
            job.portal_meta = job.portal_meta | {"notes":text(p,"notes",4000,True)}
        elif operation == "charges":
            proposal = service_memberships.charge_proposal(job.data.get("lines",[]),service_memberships.eligibility(db,actor,job).get("discountRules",[]),job.data["service"])
            if proposal != p.get("proposal"):
                raise Problem("Charges or coverage changed; review the current proposal.")
            job.portal_meta = job.portal_meta | {"appliedCharge":proposal,"reviewed":True}
        elif operation == "reverse":
            reason = text(p,"reason",500)
            visit = db.scalar(select(DispatchVisit).where(DispatchVisit.tenant_id==actor.tenant,DispatchVisit.job_id==job.id).with_for_update())
            if not visit or visit.status != "Completed" or job.data.get("work_state")=="confirmed":
                raise Problem("Only unconfirmed completed dispatch visits can be corrected here.")
            if db.scalar(select(Movement.id).where(Movement.tenant_id==actor.tenant,Movement.job_id==job.id,Movement.kind=="installed")):
                raise Problem("Installed materials require a disposition review in Work review before reopening.")
            service_memberships.reconcile(db,actor,job,False,reason)
            visit.status = "Unassigned"
            if visit.technician_id:
                tech = db.get(DispatchTechnician,(actor.tenant,visit.technician_id),with_for_update=True)
                if tech and tech.job_id==job.id:
                    tech.status,tech.job_id = "Available",None
            visit.technician_id,visit.start,visit.end,visit.travel_start,visit.date = None,None,None,None,None
            job.portal_meta = job.portal_meta | {"reviewed":False,"appliedCharge":None}
        else:
            raise Problem("Unsupported review action.",422)
        job.revision += 1
        event(db,actor,job.branch_id,"portal.job."+operation,job.id,p)
    elif kind == "customer":
        c = action.get("customer", {})
        account_type = c.get("accountType", "residential")
        if account_type not in {"residential","commercial"}:
            raise Problem("Choose a residential or business account.",422)
        name, address = text(c, "name", 80), text(c, "address", 200)
        email, phone = text(c, "email", 254, True), text(c, "phone", 80, True)
        if email and ("@" not in email or "." not in email.split("@")[-1]):
            raise Problem("Enter a valid email address.", 422)
        existing = db.get(Record, (actor.tenant, c.get("id")))
        if existing:
            existing = record(db, actor, existing.id, "customers", "write", True)
            existing.name = name
            existing.data = existing.data | {"email": email, "phone": phone, "account_type":account_type}
            existing.revision += 1
            branch = existing.branch_id
        else:
            existing = create(db, actor, "customers", branch, name, {"email": email, "phone": phone, "account_type":account_type})
            existing.portal_meta = {"verification":c.get("verification") is True}
        sites = db.scalars(select(Record).where(Record.tenant_id == actor.tenant, Record.kind == "properties", Record.parent_id == existing.id)).all()
        primary = next((s for s in sites if s.data["address"] == address), None)
        if not primary:
            primary = create(db, actor, "properties", branch, address, {"address": address}, parent_id=existing.id)
        existing.data = existing.data | {"primary_property_id": primary.id}
        event(db, actor, branch, "portal.customer.saved", existing.id, {"name": name})
    elif kind in {"create", "edit"}:
        j = action.get("job", {})
        title, description = text(j, "title", 80), text(j, "description", 500, True)
        address, requested = text(j, "address", 200), text(j, "time", 80)
        trade, node = j.get("trade"), j.get("node")
        if trade not in TRADES or node not in NODES or not isinstance(j.get("urgent", False), bool):
            raise Problem("Select a trade and a demo route destination.", 422)
        customer = record(db, actor, j.get("customerId"), "customers", "write")
        branch = customer.branch_id
        site = db.scalar(select(Record).where(Record.tenant_id == actor.tenant, Record.kind == "properties", Record.parent_id == customer.id, Record.data["address"].astext == address))
        if j.get("propertyId"):
            chosen = record(db,actor,j["propertyId"],"properties","write")
            if chosen.parent_id != customer.id or chosen.data["address"] != address:
                raise Problem("Selected property does not match the customer/address.",422)
            site = chosen
        if not site:
            site = create(db, actor, "properties", branch, address, {"address": address}, parent_id=customer.id)
        equipment = db.scalar(select(Record).where(Record.tenant_id == actor.tenant, Record.kind == "equipment", Record.parent_id == site.id, Record.data["trade"].astext == trade))
        if j.get("equipmentId"):
            equipment = record(db,actor,j["equipmentId"],"equipment","write")
            if equipment.parent_id != site.id or equipment.data["trade"] != trade:
                raise Problem("Selected equipment does not match property/trade.",422)
        if not equipment:
            equipment = create(db, actor, "equipment", branch, trade+" service", {"trade": trade}, parent_id=site.id)
        part = text(j, "part", 250)
        sku = db.scalar(select(Record).where(Record.tenant_id == actor.tenant, Record.branch_id == branch, Record.kind == "skus", Record.name == part, Record.archived.is_(False)))
        if not sku and part != "No parts required":
            raise Problem("Choose a recorded required part.", 422)
        service = j.get("service", "repair")
        if service not in {"repair","maintenance"}:
            raise Problem("Choose repair or maintenance.",422)
        try:
            service_date = datetime.fromisoformat(j.get("serviceDate") or datetime.now(timezone.utc).date().isoformat()).date().isoformat()
        except (ValueError,TypeError):
            raise Problem("Enter a service date.",422) from None
        data = {"trade": trade, "service": service, "service_date": service_date, "lines":j.get("lines",[]), "required_materials": [{"sku_id": sku.id, "quantity": 1}] if sku else []}
        if kind == "create":
            # Client-generated UUID identity permits opening the newly saved visit.
            identifier = text(j, "id", 80)
            from uuid import UUID
            try:
                UUID(identifier.removeprefix("job-"))
            except ValueError as exc:
                raise Problem("Invalid job identifier.", 422) from exc
            if db.get(Record, (actor.tenant, identifier)):
                raise Problem("Job already exists.")
            row = create(db, actor, "jobs", branch, title, data, identifier=identifier, customer_id=customer.id, property_id=site.id, equipment_id=equipment.id)
            row.portal_meta = {"verification":j.get("verification") is True, "displayNumber":str(2000+db.scalar(select(func.count()).select_from(Record).where(Record.tenant_id==actor.tenant,Record.kind=="jobs")))}
            visit = DispatchVisit(tenant_id=actor.tenant, id=uid(), branch_id=branch, job_id=row.id)
            db.add(visit)
        else:
            row = record(db, actor, j.get("id"), "jobs", "write", True)
            if row.branch_id != branch:
                raise Problem("Cannot move a job to another branch.", 403)
            visit = db.scalar(select(DispatchVisit).where(DispatchVisit.tenant_id == actor.tenant, DispatchVisit.job_id == row.id).with_for_update())
            if visit and visit.status != "Unassigned" or row.data.get("work_state") == "confirmed":
                raise Problem("Approved visits must be managed in Dispatch.")
            if not visit:
                visit = DispatchVisit(tenant_id=actor.tenant, id=uid(), branch_id=branch, job_id=row.id)
                db.add(visit)
            row.name, row.customer_id, row.property_id, row.equipment_id = title, customer.id, site.id, equipment.id
            # Keep quantities and other existing domain fields when editing a visit.
            if row.data["trade"] != trade or (row.data.get("required_materials") and row.data["required_materials"][0]["sku_id"] != (sku.id if sku else None)):
                row.data = row.data | data
            row.data = row.data | {"service":service,"service_date":service_date,"lines":crm.validate_data("jobs",data)["lines"]}
            row.revision += 1
        visit.node, visit.description, visit.requested, visit.urgent = node, description, requested, j.get("urgent", False)
        event(db, actor, branch, "portal.job.saved", row.id, {"title": title})
    elif kind == "stock":
        i = action.get("item", {})
        quantity, threshold = i.get("quantity"), i.get("threshold")
        if any(type(n) is not int or n < 0 or n > 100000 for n in [quantity, threshold]):
            raise Problem("Quantity and threshold must be nonnegative whole numbers.", 422)
        part, barcode = text(i, "part", 100), text(i, "sku", 150)
        trade = i.get("trade")
        if trade not in TRADES:
            raise Problem("Select a valid inventory trade.", 422)
        balance = db.get(Balance, (actor.tenant, i.get("id")))
        if balance:
            actor.allow(balance.branch_id, "write")
            branch = balance.branch_id
            sku = record(db, actor, balance.sku_id, "skus", "write", True)
            location = record(db, actor, balance.location_id, "locations")
            expected_name = "Warehouse" if location.data["location_type"] == "warehouse" else location.name
            if i.get("truck") != expected_name:
                raise Problem("Use a stock transfer to move recorded stock between locations.")
            if part != sku.name or barcode != sku.data.get("barcode") or trade != sku.data.get("trade"):
                crm.patch(db, actor, "skus", sku.id, {"expected_revision": sku.revision, "name": part, "data": sku.data | {"barcode": barcode, "trade": trade}})
        else:
            actor.allow(branch, "write")
            location = location_for(db, actor, branch, text(i, "truck", 100))
            sku = db.scalar(select(Record).where(Record.tenant_id == actor.tenant, Record.branch_id == branch, Record.kind == "skus", Record.name == part, Record.archived.is_(False)))
            if not sku:
                sku = create(db, actor, "skus", branch, part, {"barcode": barcode, "trade": trade})
            balance = inventory.stock(db, actor, sku.id, location.id)
            if balance.on_hand or balance.reserved:
                raise Problem("Part already exists at this location. Edit the existing stock record.")
        p = {"sku_id": sku.id, "location_id": location.id, "reason": "Portal inventory adjustment", "quantity": quantity-balance.on_hand, "action": "adjust"}
        inventory.execute(db, actor, p)
        inventory.execute(db, actor, p | {"action": "threshold", "minimum": threshold, "target": max(threshold, balance.target)})
    elif kind in {"assign", "start", "pause", "arrive", "work", "complete", "return"}:
        dispatch(db, actor, action)
    else:
        raise Problem("Unsupported database operation.", 422)
    db.flush()
    return snapshot(db, actor)


def dispatch(db, actor, action):
    tech = db.get(DispatchTechnician, (actor.tenant, action.get("techId")), with_for_update=True)
    if not tech:
        raise Problem("Technician not found.", 404)
    actor.allow(tech.branch_id, "write")
    kind = action["type"]
    if kind in {"start", "pause"} and tech.status == "Returning":
        event(db, actor, tech.branch_id, "dispatch."+kind, tech.id, {"job_id": tech.job_id})
        return
    if kind == "assign":
        job = record(db, actor, action.get("jobId"), "jobs", "write", True)
        visit = db.scalar(select(DispatchVisit).where(DispatchVisit.tenant_id == actor.tenant, DispatchVisit.job_id == job.id).with_for_update())
        if not visit or visit.node not in NODES:
            raise Problem("Edit this job to select a demo route destination before assigning.")
        if job.branch_id != tech.branch_id or job.data["trade"] != tech.trade or tech.status not in {"Available", "Completed"} or visit.status != "Unassigned":
            raise Problem("Check branch, matching trade, job status and technician availability.")
        slot = action.get("slot", {})
        start, end, travel = slot.get("start"), slot.get("end"), slot.get("travelStart")
        if any(type(n) is not int for n in [start, end, travel]) or not travel <= start < end or end-start > 4*3600000:
            raise Problem("Invalid proposed schedule.", 422)
        try:
            date = datetime.fromisoformat(slot.get("date", "")).date()
            opening = int(datetime(date.year, date.month, date.day, 9, tzinfo=timezone.utc).timestamp()*1000)
        except (ValueError, TypeError):
            raise Problem("Invalid schedule date.", 422) from None
        if travel < opening or end > opening+9*3600000:
            raise Problem("Use a schedule slot between 09:00 and 18:00.", 422)
        overlap = db.scalar(select(DispatchVisit).where(DispatchVisit.tenant_id == actor.tenant, DispatchVisit.technician_id == tech.id, DispatchVisit.travel_start < end, DispatchVisit.end > travel))
        if overlap:
            raise Problem("The proposed travel or work overlaps another visit.")
        for prerequisite in job.data.get("prerequisites", []):
            previous = db.scalar(select(DispatchVisit).where(DispatchVisit.tenant_id == actor.tenant, DispatchVisit.job_id == prerequisite))
            if not previous or previous.status != "Completed":
                raise Problem("Complete the prerequisite visit first.")
        for need in job.data.get("required_materials", []):
            inventory.execute(db, actor, {"action": "reserve", "sku_id": need["sku_id"], "location_id": tech.location_id, "job_id": job.id, "quantity": need["quantity"], "reason": "Dispatch assignment reservation"})
        job.data = job.data | {"service_date":slot["date"]}
        visit.technician_id, visit.status, visit.date, visit.start, visit.end, visit.travel_start = tech.id, "Assigned", slot["date"], start, end, travel
        tech.job_id, tech.status = job.id, "Assigned"
    elif kind == "return":
        if tech.status != "Completed":
            raise Problem("Complete work before returning.")
        tech.status = "Returning"
    elif kind == "arrive" and tech.status == "Returning":
        tech.status, tech.node, tech.job_id = "Available", "0-3", None
    else:
        visit = db.scalar(select(DispatchVisit).where(DispatchVisit.tenant_id == actor.tenant, DispatchVisit.job_id == tech.job_id).with_for_update())
        if not visit:
            raise Problem("Technician has no assigned visit.")
        allowed = {"start": ({"Assigned", "En route"}, "En route"), "pause": ({"En route", "Returning"}, tech.status), "arrive": ({"En route"}, "Arrived"), "work": ({"Arrived"}, "Working"), "complete": ({"Working"}, "Completed")}
        if kind not in allowed or tech.status not in allowed[kind][0]:
            raise Problem("This status transition is not available.")
        tech.status = allowed[kind][1]
        visit.status = tech.status
        if kind == "arrive":
            tech.node = visit.node
        if kind == "complete":
            job = record(db,actor,visit.job_id,"jobs","write",True)
            service_memberships.reconcile(db,actor,job,True,"Eligible completed dispatch maintenance")
            reservations = db.scalars(select(Reservation).where(Reservation.tenant_id == actor.tenant, Reservation.job_id == visit.job_id, Reservation.state == "active").with_for_update()).all()
            for r in reservations:
                inventory.execute(db, actor, {"action": "issue", "sku_id": r.sku_id, "location_id": r.location_id, "job_id": visit.job_id, "reservation_id": r.id, "quantity": r.quantity, "reason": "Completed dispatch work"})
            # Completion issues reserved stock. A reviewed technician note determines
            # whether each part was installed, returned or damaged.
    event(db, actor, tech.branch_id, "dispatch."+kind, tech.id, {"job_id": tech.job_id})

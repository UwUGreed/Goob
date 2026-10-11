from pydantic import ValidationError
from sqlalchemy import select

from operations.api_v1.schemas import KINDS
from operations.domain.common import Problem, dump, event, record
from operations.persistence.models import Agreement, Balance, Note, Record, uid


def validate_data(kind, data):
    if kind not in KINDS:
        raise Problem("Unknown resource type.", 404)
    try:
        return KINDS[kind].model_validate(data).model_dump(mode="json")
    except ValidationError as exc:
        raise Problem(str(exc), 422) from exc


def create(db, actor, kind, payload, identifier=None):
    actor.allow(payload["branch_id"], "write")
    permitted_links = {
        "contacts": {"parent_id"},
        "properties": {"parent_id"},
        "equipment": {"parent_id"},
        "jobs": {"customer_id", "property_id", "equipment_id"},
    }
    for field in ["parent_id", "customer_id", "property_id", "equipment_id"]:
        if payload.get(field) and field not in permitted_links.get(kind, set()):
            raise Problem("Relationship is not supported for this record type.", 422)
    data = validate_data(kind, payload.get("data", {}))
    row = Record(tenant_id=actor.tenant, id=identifier or uid(), kind=kind, **(payload | {"data": data}))
    hierarchy = {"contacts": "customers", "properties": "customers", "equipment": "properties"}
    if kind in hierarchy:
        parent = record(db, actor, row.parent_id, hierarchy[kind])
        if parent.branch_id != row.branch_id:
            raise Problem("Parent must belong to the same branch.")
    for field, expected in [
        ("customer_id", "customers"),
        ("property_id", "properties"),
        ("equipment_id", "equipment"),
    ]:
        if value := getattr(row, field):
            linked = record(db, actor, value, expected)
            if linked.branch_id != row.branch_id:
                raise Problem("Linked records must belong to the same branch.")
    if kind == "jobs":
        if not all([row.customer_id, row.property_id, row.equipment_id]):
            raise Problem("Jobs require customer, property, and equipment IDs.", 422)
        site = record(db, actor, row.property_id, "properties")
        unit = record(db, actor, row.equipment_id, "equipment")
        if (
            site.parent_id != row.customer_id
            or unit.parent_id != row.property_id
            or unit.data["trade"] != data["trade"]
        ):
            raise Problem("Job customer/property/equipment/trade do not match.")
        check_job_references(db, actor, row)
    if kind == "skus" and data["barcode"]:
        duplicate = db.scalar(
            select(Record).where(
                Record.tenant_id == actor.tenant,
                Record.kind == "skus",
                Record.data["barcode"].astext == data["barcode"],
                Record.archived.is_(False),
            )
        )
        if duplicate:
            raise Problem("Barcode already belongs to another SKU.")
    db.add(row)
    db.flush()
    event(db, actor, row.branch_id, f"{kind}.created", row.id, {"record": dump(row)})
    return dump(row)


def check_job_references(db, actor, row):
    for item in row.data["required_materials"]:
        sku = record(db, actor, item["sku_id"], "skus")
        if sku.branch_id != row.branch_id:
            raise Problem("Material is in another branch.")
    for identifier in row.data["prerequisites"]:
        linked = record(db, actor, identifier, "jobs")
        if linked.branch_id != row.branch_id or linked.id == row.id:
            raise Problem("Invalid prerequisite.")
    for line in row.data["lines"]:
        if line["sku_id"]:
            sku = record(db, actor, line["sku_id"], "skus")
            if sku.branch_id != row.branch_id:
                raise Problem("Invoice item is in another branch.")


def patch(db, actor, kind, identifier, payload):
    row = record(db, actor, identifier, kind, "write", True)
    if row.revision != payload["expected_revision"]:
        raise Problem("Record revision changed.")
    before = dump(row)
    if kind == "jobs" and row.data.get("work_state") == "confirmed":
        raise Problem("Confirmed jobs require an explicit reversal before editing.")
    if payload.get("name") is not None:
        row.name = payload["name"]
    if payload.get("data") is not None:
        row.data = validate_data(kind, payload["data"])
        if kind == "jobs":
            if record(db, actor, row.equipment_id, "equipment").data["trade"] != row.data["trade"]:
                raise Problem("Trade must match equipment.")
            check_job_references(db, actor, row)
        if kind == "equipment" and row.data["trade"] != before["data"]["trade"]:
            raise Problem("Equipment trade is immutable; create the correct equipment record.")
        if kind == "skus" and row.data.get("barcode"):
            if db.scalar(
                select(Record).where(
                    Record.tenant_id == actor.tenant,
                    Record.kind == "skus",
                    Record.id != identifier,
                    Record.data["barcode"].astext == row.data["barcode"],
                    Record.archived.is_(False),
                )
            ):
                raise Problem("Barcode already belongs to another SKU.")
    if payload.get("archived"):
        if kind == "equipment" and db.scalar(
            select(Agreement.id)
            .where(Agreement.tenant_id == actor.tenant, Agreement.equipment_id == row.id)
            .limit(1)
        ):
            raise Problem("Equipment has agreement history; retain it for coverage review.")
        if kind == "jobs" and db.scalar(
            select(Note.id).where(Note.tenant_id == actor.tenant, Note.job_id == row.id).limit(1)
        ):
            raise Problem("Jobs with recorded work cannot be archived through draft CRUD.")
        if kind in {"skus", "locations"} and db.scalar(
            select(Balance.id)
            .where(
                Balance.tenant_id == actor.tenant,
                (Balance.sku_id == row.id) | (Balance.location_id == row.id),
            )
            .limit(1)
        ):
            raise Problem(
                "Inventory records with a stock ledger must remain available for reconciliation."
            )
        children = db.scalar(
            select(Record).where(
                Record.tenant_id == actor.tenant,
                Record.archived.is_(False),
                (Record.parent_id == row.id)
                | (Record.customer_id == row.id)
                | (Record.property_id == row.id)
                | (Record.equipment_id == row.id),
            )
        )
        if children:
            raise Problem("Archive dependent records first.")
        row.archived = True
    row.revision += 1
    db.flush()
    event(
        db, actor, row.branch_id, f"{kind}.updated", row.id, {"before": before, "after": dump(row)}
    )
    return dump(row)

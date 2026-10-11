import csv
import hashlib
import io
import json

from sqlalchemy import select

from operations.api_v1.schemas import CreateAgreement, ImportRow, OpeningStock
from operations.domain import agreements, crm, inventory
from operations.domain.common import Problem, dump, event, get
from operations.persistence.models import ImportBatch, Record, uid


def csv_rows(content):
    if len(content.encode()) > 500000:
        raise Problem("CSV exceeds 500 KB.", 413)
    rows = []
    for row in csv.DictReader(io.StringIO(content)):
        row = {k: v for k, v in row.items() if v}
        try:
            row["data"] = json.loads(row.get("data", "{}"))
            rows.append(ImportRow.model_validate(row).model_dump(mode="json"))
        except (ValueError, TypeError) as exc:
            raise Problem("Invalid CSV row. The data column must contain JSON.", 422) from exc
        if len(rows) > 1000:
            raise Problem("CSV exceeds 1000 rows.", 413)
    return rows


def validate_rows(rows):
    ids = [r["source_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise Problem("Duplicate source IDs in import.", 422)
    known = set()
    issues = []
    for i, row in enumerate(rows):
        for field in ["parent_source", "customer_source", "property_source", "equipment_source"]:
            if row.get(field) and row[field] not in known:
                issues.append({"row": i, "issue": f"{field} must reference an earlier row"})
        if row["needs_review"] and not row["resolution"]:
            issues.append({"row": i, "issue": row["needs_review"]})
        try:
            if row["kind"] == "stock":
                opening = OpeningStock.model_validate(row["data"])
                if opening.sku_source not in known or opening.location_source not in known:
                    issues.append(
                        {"row": i, "issue": "Stock must reference earlier SKU and location rows."}
                    )
            elif row["kind"] != "agreements":
                crm.validate_data(row["kind"], row["data"])
            else:
                CreateAgreement.model_validate(
                    row["data"] | {"equipment_id": row.get("equipment_source") or ""}
                )
        except (Problem, ValueError) as exc:
            issues.append(
                {"row": i, "issue": str(exc) if isinstance(exc, ValueError) else exc.message}
            )
        known.add(row["source_id"])
    return issues


def stage(db, actor, branch, rows):
    actor.allow(branch, "write")
    checksum = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    existing = db.scalar(
        select(ImportBatch).where(
            ImportBatch.tenant_id == actor.tenant,
            ImportBatch.branch_id == branch,
            ImportBatch.checksum == checksum,
        )
    )
    if existing:
        return dump(existing)
    # Exact-name collisions are conservative review signals, never automatic merges.
    prepared = []
    names = set()
    for row in rows:
        row = dict(row)
        signature = (row["kind"], row["name"].casefold())
        duplicate = (
            signature in names
            or db.scalar(
                select(Record).where(
                    Record.tenant_id == actor.tenant,
                    Record.branch_id == branch,
                    Record.kind == row["kind"],
                    Record.name.ilike(row["name"]),
                    Record.archived.is_(False),
                )
            )
            is not None
        )
        if duplicate and not row["resolution"]:
            row["needs_review"] = (
                row["needs_review"] + " Possible duplicate name; verify distinct identity."
            ).strip()
        names.add(signature)
        prepared.append(row)
    batch = ImportBatch(
        tenant_id=actor.tenant,
        id=uid(),
        branch_id=branch,
        checksum=checksum,
        rows=prepared,
        report={"issues": validate_rows(prepared), "mapping_version": 1},
    )
    db.add(batch)
    db.flush()
    event(
        db, actor, branch, "import.staged", batch.id, {"checksum": checksum, "row_count": len(rows)}
    )
    return dump(batch)


def resolve(db, actor, identifier, index, replacement):
    batch = get(db, actor, ImportBatch, identifier, "write", True)
    if batch.state != "staged" or index < 0 or index >= len(batch.rows):
        raise Problem("Import row is unavailable.")
    if (
        replacement["source_id"] != batch.rows[index]["source_id"]
        or not replacement["resolution"].strip()
    ):
        raise Problem("Keep source ID and provide a resolution reason.")
    rows = list(batch.rows)
    rows[index] = replacement
    batch.rows = rows
    batch.report = {"issues": validate_rows(rows), "mapping_version": 1}
    event(
        db,
        actor,
        batch.branch_id,
        "import.resolved",
        batch.id,
        {"row": index, "reason": replacement["resolution"]},
    )
    return dump(batch)


def commit(db, actor, identifier):
    batch = get(db, actor, ImportBatch, identifier, "approve", True)
    if batch.state == "committed":
        return dump(batch)
    issues = validate_rows(batch.rows)
    if issues:
        raise Problem("Resolve every import issue before committing.")
    mapping, grants, stocks = {}, [], []
    for row in batch.rows:
        payload = {"branch_id": batch.branch_id, "name": row["name"], "data": row["data"]}
        for field in ["parent", "customer", "property", "equipment"]:
            if source := row.get(field + "_source"):
                payload[field + "_id"] = mapping[source]
        if row["kind"] == "stock":
            opening = OpeningStock.model_validate(row["data"])
            b = inventory.stock(
                db, actor, mapping[opening.sku_source], mapping[opening.location_source]
            )
            if b.on_hand or b.reserved:
                raise Problem("Opening stock requires an unused stock location/SKU balance.")
            inventory.movement(
                db,
                actor,
                b,
                None,
                "receive",
                opening.quantity,
                opening.quantity,
                "Verified migration opening balance",
            )
            mapping[row["source_id"]] = b.id
            stocks.append({"source_id": row["source_id"], "opening_quantity": opening.quantity})
        elif row["kind"] == "agreements":
            p = CreateAgreement.model_validate(
                row["data"] | {"equipment_id": payload["equipment_id"]}
            )
            result = agreements.create(db, actor, p.model_dump())
            mapping[row["source_id"]] = result["agreement"]["id"]
            grants.append({"source_id": row["source_id"], "opening_benefit": p.terms.grant})
        else:
            result = crm.create(db, actor, row["kind"], payload)
            mapping[row["source_id"]] = result["id"]
    batch.state = "committed"
    batch.report = {
        "issues": [],
        "mapping_version": 1,
        "mapping": mapping,
        "imported_count": len(mapping),
        "opening_benefits": grants,
        "opening_stock": stocks,
        "rollback": "Use audited corrective commands after operational use; no destructive batch deletion.",
    }
    event(db, actor, batch.branch_id, "import.committed", batch.id, batch.report)
    return dump(batch)

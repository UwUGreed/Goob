"""Convert the legacy export to a reviewable v1 opening-balance import.

Historical invoice/audit evidence stays in an archived copy, never fabricated as
new work. The old snapshot lacks a complete movement ledger and job relationships.
"""

import argparse
import hashlib
import json
from pathlib import Path


def convert(source, branch):
    if source.get("simulation") is not True:
        raise ValueError("This converter supports the explicit legacy demo export only.")
    if not all(source.get(k) is not None for k in ["crm", "agreements", "inventory"]):
        raise ValueError("Export must include CRM, agreements, and inventory.")
    rows, properties = [], {}
    customers = source["crm"]["customers"]
    for customer in customers:
        rows.append(
            {
                "source_id": "customer:" + customer["id"],
                "kind": "customers",
                "name": customer["name"],
                "data": {},
            }
        )
    for equipment in source["crm"]["equipment"]:
        owner = equipment.get("customer")
        if not owner:
            raise ValueError("Equipment ownership is missing; do not infer it from an address.")
        key = (owner, equipment["property"])
        if key not in properties:
            properties[key] = "property:" + str(len(properties) + 1)
            rows.append(
                {
                    "source_id": properties[key],
                    "kind": "properties",
                    "name": equipment["property"],
                    "parent_source": "customer:" + owner,
                    "data": {"address": equipment["property"]},
                }
            )
        rows.append(
            {
                "source_id": "equipment:" + equipment["id"],
                "kind": "equipment",
                "name": equipment["name"],
                "parent_source": properties[key],
                "data": {"trade": equipment["trade"]},
            }
        )
    for agreement in source["agreements"]["agreements"]:
        rows.append(
            {
                "source_id": "agreement:" + agreement["id"],
                "kind": "agreements",
                "name": "Imported " + agreement["id"],
                "equipment_source": "equipment:" + agreement["equipment"],
                "needs_review": "Verify the remaining benefit against source terms and service history before activating this opening balance.",
                "data": {
                    "trade": agreement["trade"],
                    "service": "maintenance",
                    "terms": {
                        "starts": agreement["start"],
                        "ends": agreement["end"],
                        "discount": agreement["discount"],
                        "description": agreement["terms"],
                        "grant": agreement["remaining"],
                    },
                },
            }
        )
    rows.append(
        {
            "source_id": "location:legacy",
            "kind": "locations",
            "name": "Verified legacy warehouse",
            "data": {"location_type": "warehouse"},
        }
    )
    for item in source["inventory"]:
        rows.append(
            {
                "source_id": "sku:" + item["id"],
                "kind": "skus",
                "name": item["name"],
                "data": {"cost_cents": item["cost"], "price_cents": item["price"]},
            }
        )
        rows.append(
            {
                "source_id": "stock:" + item["id"],
                "kind": "stock",
                "name": "Opening " + item["name"],
                "needs_review": "Verify physical location and available balance. Legacy export omits full material movements.",
                "data": {
                    "sku_source": "sku:" + item["id"],
                    "location_source": "location:legacy",
                    "quantity": item["available"],
                },
            }
        )
    report = {
        "source_customers": len(customers),
        "source_equipment": len(source["crm"]["equipment"]),
        "opening_benefits": {a["id"]: a["remaining"] for a in source["agreements"]["agreements"]},
        "opening_stock": {i["id"]: i["available"] for i in source["inventory"]},
        "historical_evidence_archived": {
            k: len(source.get(k, [])) for k in ["proposals", "invoices", "audit"]
        },
        "not_reconstructed": [
            "Legacy job/dispatch links",
            "Historical stock movements",
            "Historical invoice/audit events",
        ],
        "cutover": "Approve reconciled opening balances; retain original history read-only. Do not dual-write the old demo.",
    }
    return {"branch_id": branch, "rows": rows}, report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("source", type=Path)
    p.add_argument("--branch", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    raw = args.source.read_bytes()
    payload, report = convert(json.loads(raw), args.branch)
    args.output.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(raw).hexdigest()
    (args.output / f"legacy-source-{digest}.json").write_bytes(raw)
    (args.output / "staged-import.json").write_text(json.dumps(payload, indent=2))
    (args.output / "reconciliation.json").write_text(
        json.dumps(report | {"source_sha256": digest}, indent=2)
    )
    print(
        "Prepared source archive, staged-import.json and reconciliation.json. No records were imported."
    )


if __name__ == "__main__":
    main()

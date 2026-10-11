"""Run fictional data through the new API only. Does not call dispatch or voice."""

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx

from scripts.check_backend import validate_url


def run(call, branch, use_gemini=False):
    today = datetime.now(UTC).date()

    def create(kind, name, data, **links):
        return call(
            "POST", "/records/" + kind, {"branch_id": branch, "name": name, "data": data, **links}
        )

    customer = create("customers", "Fictional Morgan Ellis", {})
    site = create(
        "properties", "Fictional Oak Lane", {"address": "124 Oak Lane"}, parent_id=customer["id"]
    )
    unit = create("equipment", "Upstairs heat pump", {"trade": "HVAC"}, parent_id=site["id"])
    plumbing = create("equipment", "Kitchen plumbing", {"trade": "Plumbing"}, parent_id=site["id"])
    sku = create(
        "skus",
        "Capacitor",
        {"barcode": "DEMO-" + str(uuid4()), "price_cents": 4500, "cost_cents": 1800},
    )
    warehouse = create("locations", "Demo warehouse", {"location_type": "warehouse"})
    truck = create("locations", "Demo truck stock", {"location_type": "truck"})
    data = {
        "trade": "HVAC",
        "service": "maintenance",
        "service_date": str(today),
        "customer_approved": True,
        "billing_mode": "membership",
        "required_materials": [{"sku_id": sku["id"], "quantity": 2}],
        "lines": [
            {
                "description": "Labor",
                "kind": "labor",
                "quantity": 1,
                "unit_cents": 15000,
                "discount_eligible": True,
            },
            {
                "description": "Capacitors",
                "kind": "material",
                "sku_id": sku["id"],
                "quantity": 2,
                "unit_cents": 4500,
            },
        ],
    }
    job = create(
        "jobs",
        "Fictional maintenance",
        data,
        customer_id=customer["id"],
        property_id=site["id"],
        equipment_id=unit["id"],
    )
    agreement = call(
        "POST",
        "/agreements",
        {
            "equipment_id": unit["id"],
            "trade": "HVAC",
            "service": "maintenance",
            "terms": {
                "starts": str(today),
                "ends": str(today + timedelta(days=365)),
                "discount": 10,
                "description": "One visit, 10% eligible labor discount",
                "grant": 1,
            },
        },
    )

    def stock(action, location, quantity, **extra):
        return call(
            "POST",
            "/inventory/commands",
            {
                "action": action,
                "sku_id": sku["id"],
                "location_id": location["id"],
                "quantity": quantity,
                "reason": "Fictional award demonstration",
                **extra,
            },
        )

    before = call("GET", f"/jobs/{job['id']}/readiness")
    stock("receive", warehouse, 8)
    stock("transfer", warehouse, 2, destination_id=truck["id"])
    reservation = stock("reserve", truck, 2, job_id=job["id"])
    stock("issue", truck, 2, job_id=job["id"], reservation_id=reservation["reservation_id"])
    note = f"Maintenance completed on equipment {unit['id']}. Installed one capacitor ({sku['id']}) and returned one unused spare to truck {truck['id']}. Kitchen faucet leaks; plumbing follow-up requested."
    proposal = {"note": note, "expected_job_revision": 1}
    if not use_gemini:
        proposal["extraction"] = {
            "equipment_id": unit["id"],
            "completed_work": "HVAC maintenance",
            "completed": True,
            "unknowns": [],
            "materials": [
                {
                    "sku_id": sku["id"],
                    "location_id": truck["id"],
                    "quantity": 1,
                    "disposition": "installed",
                    "source_quote": "Installed one capacitor",
                },
                {
                    "sku_id": sku["id"],
                    "location_id": truck["id"],
                    "quantity": 1,
                    "disposition": "unused_return",
                    "source_quote": "returned one unused spare",
                },
            ],
            "followups": [
                {
                    "trade": "Plumbing",
                    "description": "Inspect kitchen faucet",
                    "source_quote": "Kitchen faucet leaks",
                }
            ],
        }
    proposed = call("POST", f"/jobs/{job['id']}/proposals", proposal)
    review = call("GET", f"/proposals/{proposed['id']}")
    # This script demonstrates preparing/reviewing. Live AI is never auto-approved.
    if use_gemini:
        return {
            "provider": "gemini",
            "review_required": True,
            "proposal": review,
            "job_id": job["id"],
        }
    approved = call(
        "POST",
        f"/proposals/{proposed['id']}/review",
        {
            "action": "approve",
            "expected_revision": 1,
            "reason": "Confirmed fictional evidence in scripted demo",
        },
    )
    return {
        "provider": "manual",
        "job_id": job["id"],
        "proposal_state": approved["state"],
        "before_readiness": before,
        "billing_preview": review["billing_preview"],
        "agreement": call("GET", f"/agreements/{agreement['agreement']['id']}"),
        "balances": call("GET", "/inventory/balances"),
        "plumbing_equipment_id": plumbing["id"],
        "history": call("GET", f"/jobs/{job['id']}/history"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, type=validate_url)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--gemini", action="store_true")
    args = parser.parse_args()
    headers = {
        "Authorization": "Bearer " + os.environ["GOOB_ACCESS_TOKEN"],
        "X-Tenant-ID": os.environ["GOOB_TENANT_ID"],
    }
    with httpx.Client(
        base_url=args.url.rstrip("/") + "/api/v1", headers=headers, timeout=60
    ) as client:

        def call(method, path, body=None):
            response = client.request(
                method, path, json=body, headers={"Idempotency-Key": str(uuid4())}
            )
            response.raise_for_status()
            return response.json()

        print(json.dumps(run(call, args.branch, args.gemini), indent=2))


if __name__ == "__main__":
    main()

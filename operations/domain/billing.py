from operations.domain.common import Problem


def review(job, coverage, materials, dismissed=None):
    dismissed = dismissed or {}
    discount = coverage.get("discount", 0) if job.data["billing_mode"] == "membership" else 0
    lines, findings, original = [], [], 0
    installed = {}
    returned = set()
    for m in materials:
        if m["disposition"] == "installed":
            installed[m["sku_id"]] = installed.get(m["sku_id"], 0) + m["quantity"]
        if m["disposition"] == "unused_return":
            returned.add(m["sku_id"])
    seen_materials = set()
    for index, line in enumerate(job.data["lines"]):
        quantity = line["quantity"]
        original += (
            quantity * line["unit_cents"]
            if line["treatment"] not in {"included", "warranty"}
            else 0
        )
        if line["kind"] == "material" and line["sku_id"]:
            if line["sku_id"] in seen_materials:
                raise Problem("Combine duplicate SKU invoice lines before review.")
            seen_materials.add(line["sku_id"])
        if (
            line["kind"] == "material"
            and line["sku_id"] in returned
            and line["treatment"] == "billable"
        ):
            proposed = min(quantity, installed.get(line["sku_id"], 0))
            if proposed < quantity:
                code = f"UNUSED_RETURN:{index}"
                findings.append(
                    {
                        "id": code,
                        "rule": "UNUSED_RETURN",
                        "line": index,
                        "proposed_quantity": proposed,
                        "source": "confirmed material disposition",
                    }
                )
                if code not in dismissed:
                    quantity = proposed
        subtotal = (
            quantity * line["unit_cents"]
            if line["treatment"] not in {"included", "warranty"}
            else 0
        )
        if coverage.get("portal_membership"):
            discount = next((r["percent"] for r in coverage.get("discountRules",[]) if r["kind"]==line["kind"] and r["service"]==job.data["service"]),0) if job.data["billing_mode"]=="membership" else 0
        reduction = 0
        if discount and line["discount_eligible"] and line["treatment"] == "billable":
            code = f"MEMBERSHIP_DISCOUNT:{index}"
            findings.append(
                {
                    "id": code,
                    "rule": "MEMBERSHIP_DISCOUNT",
                    "line": index,
                    "terms_id": coverage["terms_id"],
                    "percent": discount,
                }
            )
            if code not in dismissed:
                reduction = (subtotal * discount + 50) // 100
        lines.append(
            line
            | {
                "quantity": quantity,
                "subtotal_cents": subtotal,
                "discount_cents": reduction,
                "total_cents": subtotal - reduction,
            }
        )
    for sku in installed.keys() - seen_materials:
        findings.append(
            {
                "id": f"MATERIAL_NOT_ON_DRAFT:{sku}",
                "rule": "MATERIAL_NOT_ON_DRAFT",
                "sku_id": sku,
                "quantity": installed[sku],
                "action": "review; no automatic charge",
            }
        )
    valid = {f["id"] for f in findings}
    if any(key not in valid or not reason.strip() for key, reason in dismissed.items()):
        raise Problem("Dismissals require a current finding ID and a reason.")
    unresolved = [
        f for f in findings if f["rule"] == "MATERIAL_NOT_ON_DRAFT" and f["id"] not in dismissed
    ]
    return {
        "currency": job.data["currency"],
        "lines": lines,
        "original_cents": original,
        "approved_cents": sum(line["total_cents"] for line in lines),
        "tax_cents": 0,
        "tax_status": "not_calculated_draft_only",
        "coverage": coverage,
        "findings": findings,
        "dismissed_findings": dismissed,
        "unresolved": unresolved,
    }

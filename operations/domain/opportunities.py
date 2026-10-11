from operations.domain import crm
from operations.domain.common import Problem, dump, event, record


def convert(db, actor, identifier, payload):
    opportunity = record(db, actor, identifier, "opportunities", "write", True)
    if opportunity.data["state"] == "converted":
        return {"job_id": opportunity.data["job_id"], "replayed": True}
    if opportunity.data["state"] == "dismissed":
        raise Problem("Dismissed opportunities cannot be converted.")
    if payload["data"]["trade"] != opportunity.data["trade"]:
        raise Problem("Follow-up trade must match the reviewed opportunity.")
    result = crm.create(
        db,
        actor,
        "jobs",
        {
            "branch_id": opportunity.branch_id,
            "name": opportunity.name,
            "customer_id": opportunity.customer_id,
            "property_id": opportunity.property_id,
            "equipment_id": payload["equipment_id"],
            "data": payload["data"],
        },
    )
    opportunity.data = opportunity.data | {"state": "converted", "job_id": result["id"]}
    opportunity.revision += 1
    event(
        db,
        actor,
        opportunity.branch_id,
        "opportunity.converted",
        opportunity.id,
        {"job_id": result["id"], "source_job_id": opportunity.data["source_job_id"]},
    )
    return {"job_id": result["id"], "opportunity": dump(opportunity)}

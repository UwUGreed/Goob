"""Reserve bounded provider attempts before the external call; effects remain separate."""

import hashlib
import json
import os
from datetime import timedelta

from sqlalchemy import func, select, text

from operations.domain.common import Problem, event, record
from operations.domain.identity import actor_for
from operations.persistence.models import Command, Event, now


def reserve(db, actor, job_id, key, payload):
    if not key or len(key) > 160:
        raise Problem("Idempotency-Key of 1–160 characters is required.", 400)
    fingerprint = hashlib.sha256(
        json.dumps(
            [actor.subject, "propose:" + job_id, payload], sort_keys=True, default=str
        ).encode()
    ).hexdigest()
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:tenant, 0))"), {"tenant": actor.tenant}
    )
    db.expire_all()
    if actor_for(db, actor.tenant, actor.subject) != actor:
        raise Problem("Authorization changed.", 403)
    job = record(db, actor, job_id, "jobs", "propose")
    existing = db.get(Command, (actor.tenant, key))
    if existing:
        if existing.fingerprint != fingerprint:
            raise Problem("Idempotency key already used for a different request.")
        return existing.result
    if (
        job.revision != payload["expected_job_revision"]
        or job.data.get("work_state") == "confirmed"
    ):
        raise Problem("Job changed; refresh before requesting AI.")
    count = db.scalar(
        select(func.count())
        .select_from(Event)
        .where(
            Event.tenant_id == actor.tenant,
            Event.kind == "ai.attempt",
            Event.created_at >= now() - timedelta(hours=1),
        )
    )
    if count >= int(os.environ.get("GEMINI_HOURLY_REQUEST_LIMIT", "30")):
        raise Problem("Company AI request allowance exhausted for this hour.", 429)
    event(db, actor, job.branch_id, "ai.attempt", job.id, {"request_fingerprint": fingerprint})
    db.commit()
    return None

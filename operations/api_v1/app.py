import logging
import os
from datetime import date, datetime, timedelta
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from operations.api_v1.auth import OIDCVerifier
from operations.api_v1.schemas import (
    AgreementCommand,
    CreateAgreement,
    CreateRecord,
    ImportRequest,
    ImportRow,
    InventoryCommand,
    Job,
    MemberRequest,
    NewProposal,
    PatchRecord,
    Review,
    Strict,
)
from operations.domain import (
    agreements,
    ai_usage,
    analytics,
    billing,
    crm,
    identity,
    imports,
    inventory,
    opportunities,
    readiness,
    workflow,
    workspace,
)
from operations.domain.common import Problem, command, dump, event, get, module, record
from operations.integrations.gemini import Gemini
from operations.persistence.database import engine_for, sessions
from operations.persistence.models import (
    Agreement,
    Benefit,
    Event,
    ImportBatch,
    Invoice,
    Movement,
    Note,
    Outbox,
    Proposal,
    Record,
    ServicePlan,
    Terms,
    now,
    uid,
)
from operations.persistence.readiness import check_schema


class Reason(Strict):
    reason: str = Field(min_length=1, max_length=1000)


class CSVImport(Strict):
    branch_id: str
    csv: str = Field(max_length=500000)


class Modules(Strict):
    enabled: list[str]


class Conversion(Strict):
    equipment_id: str
    data: Job


class MessageDraft(Strict):
    branch_id: str
    customer_id: str
    channel: str = Field(pattern="^(email|sms)$")
    text: str = Field(min_length=1, max_length=5000)


class LeadIntake(Strict):
    branch_id: str
    name: str = Field(min_length=1, max_length=250)
    address: str = Field(min_length=1, max_length=500)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=80)
    trade: str = Field(pattern="^(HVAC|Plumbing|Electrical)$")
    service: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=1000)


class ExistingOpportunity(Strict):
    branch_id: str
    customer_id: str
    property_id: str
    trade: str = Field(pattern="^(HVAC|Plumbing|Electrical)$")
    service: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=1000)


def create_app(engine=None, verifier=None, gemini=None):
    engine = engine if engine is not None else engine_for()
    def unavailable_verifier(token):
        raise Problem("OIDC bearer authentication is not configured.", 401)
    verify = verifier or (OIDCVerifier() if os.environ.get("OIDC_ISSUER") else unavailable_verifier)
    factory = sessions(engine)
    provider = gemini or Gemini()
    app = FastAPI(
        title="Goob Operations API",
        version="1.0.0",
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[v.strip() for v in os.environ.get("ALLOWED_ORIGINS", "").split(",") if v.strip()],
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "Idempotency-Key"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id(request, call_next):
        request.state.request_id = str(uuid4())
        if request.method in {"POST", "PATCH", "DELETE"} and not request.headers.get("authorization"):
            origin = request.headers.get("origin")
            origins = {str(request.base_url).rstrip("/")}
            configured = os.environ.get("GOOB_PUBLIC_ORIGIN")
            if configured:
                origins.add(configured.rstrip("/"))
            # Vite forwards same-origin browser requests to the Python server.
            # Both loopback names are supported for the two local application ports.
            if os.environ.get("GOOB_ENV") != "production":
                origins.update(f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (5173, 8090))
            if request.headers.get("sec-fetch-site") == "cross-site" or (origin and origin not in origins):
                return JSONResponse(status_code=403, content={"error": "Cross-origin request rejected."})
            if "application/json" not in request.headers.get("content-type", ""):
                return JSONResponse(status_code=415, content={"error": "JSON requests are required."})
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 1000000):
            return JSONResponse(status_code=413, content={"error": "Request exceeds 1 MB."})
        # Check actual bytes too, including chunked requests, before JSON parsing.
        if request.method in {"POST", "PATCH"}:
            size, chunks = 0, []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 1000000:
                    return JSONResponse(status_code=413, content={"error": "Request exceeds 1 MB."})
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(Problem)
    async def problem(request, exc):
        return JSONResponse(
            status_code=exc.status,
            content={"error": exc.message, "request_id": request.state.request_id},
        )

    @app.exception_handler(RequestValidationError)
    async def validation(request, exc):
        return JSONResponse(
            status_code=422,
            content={
                "error": "Invalid request fields.",
                "fields": [{"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()],
                "request_id": request.state.request_id,
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity(request, exc):
        return JSONResponse(
            status_code=409,
            content={
                "error": "Record conflict or invalid relationship.",
                "request_id": request.state.request_id,
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        logging.getLogger("goob").error("Database request failed: %s", request.state.request_id)
        return JSONResponse(
            status_code=503,
            content={"error": "Database unavailable.", "request_id": request.state.request_id},
        )

    def session():
        with factory() as db:
            yield db

    def actor(
        request: Request,
        db=Depends(session),
        credentials=Depends(HTTPBearer(auto_error=False)),
        x_tenant_id: str = Header(default=""),
    ):
        if credentials is None:
            from operations.api_v1.portal_auth import session_user
            return session_user(db, request)[1]
        if not x_tenant_id:
            raise Problem("Bearer authentication and X-Tenant-ID are required.", 401)
        return identity.actor_for(db, x_tenant_id, verify(credentials.credentials))

    def mutate(db, user, key, operation, payload, run):
        result = command(db, user, key, operation, payload, run)
        db.commit()
        return result

    def check(db, user, name):
        module(db, user, name)
        db.info.setdefault("required_modules", set()).add(name)

    @app.get("/health/live")
    def live():
        return {"status": "live"}

    @app.get("/health/ready")
    def ready():
        try:
            with engine.connect() as conn:
                check_schema(conn)
            return {"status": "ready"}
        except (SQLAlchemyError, RuntimeError):
            return JSONResponse(status_code=503, content={"status": "unready"})

    prefix = "/api/v1"

    @app.get(prefix + "/me")
    def me(user=Depends(actor)):
        return {
            "subject": user.subject,
            "tenant_id": user.tenant,
            "role": user.role,
            "branches": user.branches,
        }

    @app.get(prefix + "/records/{kind}")
    def list_records(
        kind: str,
        q: str = Query(default="", max_length=100),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        db=Depends(session),
        user=Depends(actor),
    ):
        if kind not in crm.KINDS and kind != "opportunities":
            raise Problem("Unknown resource.", 404)
        check(
            db,
            user,
            "jobs"
            if kind == "jobs"
            else "inventory"
            if kind in {"skus", "locations"}
            else "opportunities"
            if kind == "opportunities"
            else "crm",
        )
        query = select(Record).where(
            Record.tenant_id == user.tenant,
            Record.branch_id.in_(user.branches),
            Record.kind == kind,
            Record.archived.is_(False),
        )
        if q:
            query = query.where(Record.name.icontains(q, autoescape=True))
        return [dump(r) for r in db.scalars(query.order_by(Record.id).limit(limit).offset(offset))]

    @app.post(prefix + "/records/{kind}", status_code=201)
    def create_record(
        kind: str,
        body: CreateRecord,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        check(
            db,
            user,
            "jobs" if kind == "jobs" else "inventory" if kind in {"skus", "locations"} else "crm",
        )
        p = body.model_dump()
        return mutate(
            db, user, idempotency_key, "create:" + kind, p, lambda: crm.create(db, user, kind, p)
        )

    @app.get(prefix + "/records/{kind}/{identifier}")
    def read_record(kind: str, identifier: str, db=Depends(session), user=Depends(actor)):
        check(
            db,
            user,
            "jobs"
            if kind == "jobs"
            else "inventory"
            if kind in {"skus", "locations"}
            else "opportunities"
            if kind == "opportunities"
            else "crm",
        )
        return dump(record(db, user, identifier, kind))

    @app.patch(prefix + "/records/{kind}/{identifier}")
    def patch_record(
        kind: str,
        identifier: str,
        body: PatchRecord,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        if kind not in crm.KINDS:
            raise Problem("Unknown resource.", 404)
        check(
            db,
            user,
            "jobs" if kind == "jobs" else "inventory" if kind in {"skus", "locations"} else "crm",
        )
        p = body.model_dump()
        return mutate(
            db,
            user,
            idempotency_key,
            f"patch:{kind}:{identifier}",
            p,
            lambda: crm.patch(db, user, kind, identifier, p),
        )

    @app.post(prefix + "/agreements", status_code=201)
    def new_agreement(
        body: CreateAgreement,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        check(db, user, "agreements")
        p = body.model_dump()
        return mutate(
            db, user, idempotency_key, "agreement:create", p, lambda: agreements.create(db, user, p)
        )

    @app.get(prefix + "/agreements")
    def list_agreements(db=Depends(session), user=Depends(actor)):
        check(db, user, "agreements")
        return [
            dump(row) | {"remaining": agreements.balance(db, user.tenant, row.id)}
            for row in db.scalars(
                select(Agreement).where(
                    Agreement.tenant_id == user.tenant,
                    Agreement.branch_id.in_(user.branches),
                ).order_by(Agreement.id)
            )
        ]

    @app.get(prefix + "/agreements/{identifier}")
    def read_agreement(identifier: str, db=Depends(session), user=Depends(actor)):
        check(db, user, "agreements")
        row = get(db, user, Agreement, identifier)
        return {
            "agreement": dump(row),
            "remaining": agreements.balance(db, user.tenant, identifier),
            "terms": [
                dump(t)
                for t in db.scalars(
                    select(Terms)
                    .where(Terms.tenant_id == user.tenant, Terms.agreement_id == identifier)
                    .order_by(Terms.starts)
                )
            ],
            "ledger": [
                dump(b)
                for b in db.scalars(
                    select(Benefit).where(
                        Benefit.tenant_id == user.tenant, Benefit.agreement_id == identifier
                    )
                )
            ],
        }

    @app.post(prefix + "/agreements/{identifier}/commands")
    def agreement_command(
        identifier: str,
        body: AgreementCommand,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        check(db, user, "agreements")
        p = body.model_dump()
        return mutate(
            db,
            user,
            idempotency_key,
            "agreement:" + identifier,
            p,
            lambda: agreements.change(db, user, identifier, p),
        )

    @app.get(prefix + "/jobs/{identifier}/coverage")
    def job_coverage(identifier: str, db=Depends(session), user=Depends(actor)):
        check(db, user, "agreements")
        return agreements.coverage(db, user, record(db, user, identifier, "jobs"))

    @app.get(prefix + "/obligations")
    def obligations(as_of: date | None = None, db=Depends(session), user=Depends(actor)):
        check(db, user, "agreements")
        return agreements.obligations(db, user, as_of or now().date())

    @app.get(prefix + "/equipment/{identifier}/history")
    def equipment_history(identifier: str, db=Depends(session), user=Depends(actor)):
        check(db, user, "workflow")
        record(db, user, identifier, "equipment")
        return [
            dump(r)
            for r in db.scalars(
                select(Event)
                .where(
                    Event.tenant_id == user.tenant,
                    Event.branch_id.in_(user.branches),
                    Event.evidence["equipment_id"].astext == identifier,
                )
                .order_by(Event.created_at)
            )
        ]

    @app.get(prefix + "/invoices/{identifier}/accounting-export")
    def accounting_export(identifier: str, db=Depends(session), user=Depends(actor)):
        check(db, user, "billing")
        invoice = get(db, user, Invoice, identifier, "approve")
        approval = get(db, user, Proposal, invoice.proposal_id)
        if approval.state != "approved":
            raise Problem(
                "This draft approval was reversed or superseded; review the current draft."
            )
        return {
            "schema_version": 1,
            "external_source_id": "goob:" + invoice.id,
            "job_id": invoice.job_id,
            "state": "approved_draft",
            "snapshot": invoice.snapshot,
            "sync_status": "not_posted",
            "tax_review_required": True,
        }

    @app.post(prefix + "/inventory/commands")
    def inventory_command(
        body: InventoryCommand,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        check(db, user, "inventory")
        p = body.model_dump()
        return mutate(
            db, user, idempotency_key, "inventory", p, lambda: inventory.execute(db, user, p)
        )

    @app.get(prefix + "/inventory/balances")
    def stock_balances(db=Depends(session), user=Depends(actor)):
        check(db, user, "inventory")
        return inventory.balances(db, user)

    @app.get(prefix + "/inventory/barcodes/{barcode}")
    def barcode_lookup(barcode: str, db=Depends(session), user=Depends(actor)):
        check(db, user, "inventory")
        return [
            dump(r)
            for r in db.scalars(
                select(Record).where(
                    Record.tenant_id == user.tenant,
                    Record.branch_id.in_(user.branches),
                    Record.kind == "skus",
                    Record.archived.is_(False),
                    Record.data["barcode"].astext == barcode,
                )
            )
        ]

    @app.post(prefix + "/jobs/{identifier}/proposals", status_code=201)
    def propose(
        identifier: str,
        body: NewProposal,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        check(db, user, "workflow")
        p = body.model_dump(mode="json")
        extracted = metadata = None
        if body.extraction is None:
            cached = ai_usage.reserve(db, user, identifier, idempotency_key, p)
            if cached is not None:
                return cached
            job = record(db, user, identifier, "jobs", "propose")
            context = {
                "job": dump(job),
                "equipment": dump(record(db, user, job.equipment_id, "equipment")),
                "catalog": [
                    dump(r)
                    for r in db.scalars(
                        select(Record)
                        .where(
                            Record.tenant_id == user.tenant,
                            Record.branch_id == job.branch_id,
                            Record.kind.in_(["skus", "locations"]),
                            Record.archived.is_(False),
                        )
                        .limit(101)
                    )
                ],
            }
            if len(context["catalog"]) > 100:
                raise Problem("Narrow the catalog before AI extraction.", 422)
            # Release the read transaction before the network request.
            db.rollback()
            extracted, metadata = provider.extract(body.note, context)
        return mutate(
            db,
            user,
            idempotency_key,
            "propose:" + identifier,
            p,
            lambda: workflow.prepare(db, user, identifier, p, extracted, metadata),
        )

    @app.get(prefix + "/proposals/{identifier}")
    def read_proposal(identifier: str, db=Depends(session), user=Depends(actor)):
        check(db, user, "workflow")
        p = get(db, user, Proposal, identifier)
        job = record(db, user, p.job_id, "jobs")
        invoice = db.scalar(
            select(Invoice).where(
                Invoice.tenant_id == user.tenant, Invoice.proposal_id == identifier
            )
        )
        return {
            "proposal": dump(p),
            "note": dump(get(db, user, Note, p.note_id)),
            "billing_preview": invoice.snapshot
            if invoice
            else billing.review(job, agreements.coverage(db, user, job), p.extraction["materials"]),
        }

    @app.post(prefix + "/proposals/{identifier}/review")
    def review_proposal(
        identifier: str,
        body: Review,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        check(db, user, "workflow")
        p = body.model_dump(mode="json")
        return mutate(
            db,
            user,
            idempotency_key,
            "review:" + identifier,
            p,
            lambda: workflow.review(db, user, identifier, p),
        )

    @app.post(prefix + "/jobs/{identifier}/reverse")
    def reverse_job(
        identifier: str,
        body: Reason,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        check(db, user, "workflow")
        return mutate(
            db,
            user,
            idempotency_key,
            "reverse:" + identifier,
            body.model_dump(),
            lambda: workflow.reverse(db, user, identifier, body.reason),
        )

    @app.get(prefix + "/jobs/{identifier}/history")
    def history(identifier: str, db=Depends(session), user=Depends(actor)):
        check(db, user, "workflow")
        record(db, user, identifier, "jobs")
        return {
            "notes": [
                dump(r)
                for r in db.scalars(
                    select(Note).where(Note.tenant_id == user.tenant, Note.job_id == identifier)
                )
            ],
            "invoices": [
                dump(r)
                for r in db.scalars(
                    select(Invoice).where(
                        Invoice.tenant_id == user.tenant, Invoice.job_id == identifier
                    )
                )
            ],
            "events": [
                dump(r)
                for r in db.scalars(
                    select(Event)
                    .where(Event.tenant_id == user.tenant, Event.resource_id == identifier)
                    .order_by(Event.created_at)
                )
            ],
        }

    @app.get(prefix + "/jobs/{identifier}/readiness")
    def job_readiness(identifier: str, db=Depends(session), user=Depends(actor)):
        check(db, user, "readiness")
        return readiness.evaluate(db, user, identifier)

    @app.get(prefix + "/jobs/{identifier}/workspace")
    def job_workspace(
        identifier: str,
        limit: int = Query(default=50, ge=1, le=100),
        db=Depends(session),
        user=Depends(actor),
    ):
        return workspace.read(db, user, identifier, limit)

    @app.post(prefix + "/imports")
    def stage_import(
        body: ImportRequest,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        check(db, user, "imports")
        p = body.model_dump(mode="json")
        return mutate(
            db,
            user,
            idempotency_key,
            "import:stage",
            p,
            lambda: imports.stage(db, user, p["branch_id"], p["rows"]),
        )

    @app.post(prefix + "/imports/csv")
    def stage_csv(
        body: CSVImport,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        check(db, user, "imports")
        rows = imports.csv_rows(body.csv)
        p = ImportRequest(branch_id=body.branch_id, rows=rows).model_dump(mode="json")
        return mutate(
            db,
            user,
            idempotency_key,
            "import:stage",
            p,
            lambda: imports.stage(db, user, body.branch_id, p["rows"]),
        )

    @app.get(prefix + "/imports")
    def list_imports(db=Depends(session), user=Depends(actor)):
        check(db, user, "imports")
        return [
            dump(row) for row in db.scalars(
                select(ImportBatch).where(
                    ImportBatch.tenant_id == user.tenant,
                    ImportBatch.branch_id.in_(user.branches),
                ).order_by(ImportBatch.id.desc()).limit(100)
            )
        ]

    @app.get(prefix + "/imports/{identifier}")
    def read_import(identifier: str, db=Depends(session), user=Depends(actor)):
        check(db, user, "imports")
        return dump(get(db, user, ImportBatch, identifier))

    @app.post(prefix + "/imports/{identifier}/rows/{index}")
    def resolve_import(
        identifier: str,
        index: int,
        body: ImportRow,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        check(db, user, "imports")
        p = body.model_dump(mode="json")
        return mutate(
            db,
            user,
            idempotency_key,
            f"import:resolve:{identifier}:{index}",
            p,
            lambda: imports.resolve(db, user, identifier, index, p),
        )

    @app.post(prefix + "/imports/{identifier}/commit")
    def commit_import(
        identifier: str,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        check(db, user, "imports")
        return mutate(
            db,
            user,
            idempotency_key,
            "import:commit:" + identifier,
            {},
            lambda: imports.commit(db, user, identifier),
        )

    @app.post(prefix + "/opportunities/{identifier}/convert")
    def convert_opportunity(
        identifier: str,
        body: Conversion,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        check(db, user, "opportunities")
        p = body.model_dump(mode="json")
        return mutate(
            db,
            user,
            idempotency_key,
            "opportunity:convert:" + identifier,
            p,
            lambda: opportunities.convert(db, user, identifier, p),
        )

    @app.post(prefix + "/opportunities", status_code=201)
    def create_opportunity(body: ExistingOpportunity, idempotency_key: str = Header(default=""), db=Depends(session), user=Depends(actor)):
        check(db, user, "opportunities")
        p = body.model_dump()

        def run():
            customer = record(db, user, p["customer_id"], "customers", "write")
            property_record = record(db, user, p["property_id"], "properties", "write")
            if customer.branch_id != p["branch_id"] or property_record.branch_id != p["branch_id"] or property_record.parent_id != customer.id:
                raise Problem("Select a property belonging to this customer and branch.", 422)
            opportunity = Record(
                tenant_id=user.tenant, id=uid(), branch_id=p["branch_id"],
                kind="opportunities", name=p["description"][:250],
                customer_id=customer.id, property_id=property_record.id,
                data={"trade": p["trade"], "service": p["service"],
                      "description": p["description"], "state": "reviewed", "source_job_id": None},
            )
            db.add(opportunity)
            db.flush()
            event(db, user, p["branch_id"], "opportunity.created", opportunity.id, {"customer_id": customer.id})
            return dump(opportunity)

        return mutate(db, user, idempotency_key, "opportunity:create", p, run)

    @app.post(prefix + "/leads", status_code=201)
    def capture_lead(body: LeadIntake, idempotency_key: str = Header(default=""), db=Depends(session), user=Depends(actor)):
        check(db, user, "opportunities")
        p = body.model_dump()

        def run():
            user.allow(p["branch_id"], "write")
            customer = crm.create(db, user, "customers", {
                "branch_id": p["branch_id"], "name": p["name"],
                "data": {"email": p["email"], "phone": p["phone"]},
            })
            property_record = crm.create(db, user, "properties", {
                "branch_id": p["branch_id"], "name": p["address"],
                "parent_id": customer["id"], "data": {"address": p["address"]},
            })
            lead = Record(
                tenant_id=user.tenant, id=uid(), branch_id=p["branch_id"],
                kind="opportunities", name=p["description"][:250],
                customer_id=customer["id"], property_id=property_record["id"],
                data={"trade": p["trade"], "service": p["service"],
                      "description": p["description"], "state": "reviewed", "source_job_id": None},
            )
            db.add(lead)
            db.flush()
            event(db, user, p["branch_id"], "lead.captured", lead.id, {"customer_id": customer["id"]})
            return {"lead": dump(lead), "customer": customer, "property": property_record}

        return mutate(db, user, idempotency_key, "lead:capture", p, run)

    @app.post(prefix + "/opportunities/{identifier}/dismiss")
    def dismiss_opportunity(
        identifier: str,
        body: Reason,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        check(db, user, "opportunities")

        def run():
            row = record(db, user, identifier, "opportunities", "write", True)
            if row.data["state"] == "converted":
                raise Problem("Opportunity already converted.")
            row.data = row.data | {"state": "dismissed", "reason": body.reason}
            row.revision += 1
            event(db, user, row.branch_id, "opportunity.dismissed", row.id, body.model_dump())
            return dump(row)

        return mutate(
            db, user, idempotency_key, "opportunity:dismiss:" + identifier, body.model_dump(), run
        )

    @app.post(prefix + "/admin/members/{subject}")
    def set_member(
        subject: str,
        body: MemberRequest,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        p = body.model_dump()

        def run():
            result = identity.update_member(db, user, subject, p)
            for branch in p["branches"]:
                event(db, user, branch, "identity.membership_updated", subject, p)
            return result

        return mutate(db, user, idempotency_key, "member:" + subject, p, run)

    @app.post(prefix + "/admin/modules")
    def set_modules(
        body: Modules,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        def run():
            result = identity.configure(db, user, body.enabled)
            for branch in user.branches:
                event(db, user, branch, "modules.configured", user.tenant, result)
            return result

        return mutate(db, user, idempotency_key, "modules", body.model_dump(), run)

    @app.get(prefix + "/analytics")
    def operational_report(
        start: datetime | None = None,
        end: datetime | None = None,
        db=Depends(session),
        user=Depends(actor),
    ):
        check(db, user, "analytics")
        end = end or now()
        start = start or end - timedelta(days=30)
        if not start.tzinfo or not end.tzinfo or start >= end or end - start > timedelta(days=366):
            raise Problem("Use timezone-aware dates spanning at most 366 days.", 422)
        return analytics.report(db, user, start, end)

    @app.get(prefix + "/export")
    def export(db=Depends(session), user=Depends(actor)):
        if user.role not in {"owner", "office"}:
            raise Problem("Office or owner permission required for export.", 403)
        result = {"schema_version": 1, "exported_at": now().isoformat()}
        for model in [
            Record,
            ServicePlan,
            Agreement,
            Terms,
            Benefit,
            Movement,
            Note,
            Proposal,
            Invoice,
            Event,
            ImportBatch,
        ]:
            result[model.__tablename__] = [
                dump(r)
                for r in db.scalars(
                    select(model).where(
                        model.tenant_id == user.tenant, model.branch_id.in_(user.branches)
                    )
                )
            ]
        return result

    @app.post(prefix + "/message-drafts")
    def message_draft(
        body: MessageDraft,
        idempotency_key: str = Header(default=""),
        db=Depends(session),
        user=Depends(actor),
    ):
        check(db, user, "crm")

        def run():
            customer = record(db, user, body.customer_id, "customers", "write")
            if customer.branch_id != body.branch_id:
                raise Problem("Customer branch mismatch.")
            row = Outbox(
                tenant_id=user.tenant,
                id=uid(),
                branch_id=body.branch_id,
                channel=body.channel,
                payload=body.model_dump(),
            )
            db.add(row)
            db.flush()
            event(
                db,
                user,
                body.branch_id,
                "message.drafted",
                row.id,
                {"customer_id": body.customer_id, "channel": body.channel},
            )
            return dump(row) | {"delivery": "not_sent"}

        return mutate(db, user, idempotency_key, "message:draft", body.model_dump(), run)

    from operations.api_v1.portal import register_portal
    register_portal(app, factory, session, actor)
    return app

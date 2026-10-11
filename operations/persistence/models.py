"""PostgreSQL records. Composite references prevent cross-tenant relationships."""

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid4())


def now():
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants_v1"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str]
    modules: Mapped[list] = mapped_column(
        JSONB,
        default=lambda: [
            "crm",
            "jobs",
            "agreements",
            "inventory",
            "billing",
            "workflow",
            "imports",
            "readiness",
            "opportunities",
            "analytics",
        ],
    )


class Branch(Base):
    __tablename__ = "branches_v1"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants_v1.id"), primary_key=True)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str]


class Membership(Base):
    __tablename__ = "memberships_v1"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants_v1.id"), primary_key=True)
    subject: Mapped[str] = mapped_column(String, primary_key=True)
    role: Mapped[str]
    branches: Mapped[list] = mapped_column(JSONB, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Scoped:
    tenant_id: Mapped[str] = mapped_column(String, primary_key=True)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    branch_id: Mapped[str]


def branch_fk():
    return ForeignKeyConstraint(
        ["tenant_id", "branch_id"], ["branches_v1.tenant_id", "branches_v1.id"]
    )


def record_fk(field):
    return ForeignKeyConstraint(["tenant_id", field], ["records_v1.tenant_id", "records_v1.id"])


class Record(Scoped, Base):
    """Typed CRM/job/catalog records; schemas and hierarchy are validated by domain services."""

    __tablename__ = "records_v1"
    kind: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str]
    parent_id: Mapped[str | None] = mapped_column(String)
    customer_id: Mapped[str | None] = mapped_column(String)
    property_id: Mapped[str | None] = mapped_column(String)
    equipment_id: Mapped[str | None] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        branch_fk(),
        record_fk("parent_id"),
        record_fk("customer_id"),
        record_fk("property_id"),
        record_fk("equipment_id"),
    )


class Agreement(Scoped, Base):
    __tablename__ = "agreements_v1"
    equipment_id: Mapped[str]
    trade: Mapped[str]
    service: Mapped[str]
    status: Mapped[str] = mapped_column(String, default="active")
    canceled_on: Mapped[datetime | None] = mapped_column(Date)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (branch_fk(), record_fk("equipment_id"))


class Terms(Scoped, Base):
    __tablename__ = "terms_v1"
    agreement_id: Mapped[str]
    starts: Mapped[datetime] = mapped_column(Date)
    ends: Mapped[datetime] = mapped_column(Date)
    discount: Mapped[int]
    description: Mapped[str]
    due_dates: Mapped[list] = mapped_column(JSONB, default=list)
    __table_args__ = (
        branch_fk(),
        ForeignKeyConstraint(
            ["tenant_id", "agreement_id"], ["agreements_v1.tenant_id", "agreements_v1.id"]
        ),
        CheckConstraint("starts <= ends"),
        CheckConstraint("discount >= 0 AND discount <= 100"),
    )


class Benefit(Scoped, Base):
    __tablename__ = "benefits_v1"
    agreement_id: Mapped[str]
    job_id: Mapped[str | None] = mapped_column(String)
    amount: Mapped[int]
    reason: Mapped[str]
    effective_on: Mapped[date] = mapped_column(Date, default=lambda: now().date())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        branch_fk(),
        ForeignKeyConstraint(
            ["tenant_id", "agreement_id"], ["agreements_v1.tenant_id", "agreements_v1.id"]
        ),
        record_fk("job_id"),
    )


class Balance(Scoped, Base):
    __tablename__ = "balances_v1"
    sku_id: Mapped[str]
    location_id: Mapped[str]
    on_hand: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    minimum: Mapped[int] = mapped_column(Integer, default=0)
    target: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        branch_fk(),
        record_fk("sku_id"),
        record_fk("location_id"),
        UniqueConstraint("tenant_id", "sku_id", "location_id"),
        CheckConstraint("on_hand >= 0 AND reserved >= 0 AND reserved <= on_hand"),
        CheckConstraint("minimum >= 0 AND target >= minimum"),
    )


class Reservation(Scoped, Base):
    __tablename__ = "reservations_v1"
    job_id: Mapped[str]
    sku_id: Mapped[str]
    location_id: Mapped[str]
    quantity: Mapped[int]
    state: Mapped[str] = mapped_column(String, default="active")
    __table_args__ = (
        branch_fk(),
        record_fk("job_id"),
        record_fk("sku_id"),
        record_fk("location_id"),
        CheckConstraint("quantity > 0"),
    )


class Movement(Scoped, Base):
    __tablename__ = "movements_v1"
    sku_id: Mapped[str]
    location_id: Mapped[str]
    job_id: Mapped[str | None] = mapped_column(String)
    kind: Mapped[str]
    quantity: Mapped[int]
    delta: Mapped[int]
    reason: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        branch_fk(),
        record_fk("sku_id"),
        record_fk("location_id"),
        record_fk("job_id"),
    )


class Note(Scoped, Base):
    __tablename__ = "notes_v1"
    job_id: Mapped[str]
    text: Mapped[str]
    actor: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (branch_fk(), record_fk("job_id"))


class Proposal(Scoped, Base):
    __tablename__ = "proposals_v1"
    job_id: Mapped[str]
    note_id: Mapped[str]
    job_revision: Mapped[int]
    revision: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String, default="pending")
    extraction: Mapped[dict] = mapped_column(JSONB)
    provider: Mapped[str]
    provider_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    parent_id: Mapped[str | None] = mapped_column(String)
    __table_args__ = (
        branch_fk(),
        record_fk("job_id"),
        ForeignKeyConstraint(["tenant_id", "note_id"], ["notes_v1.tenant_id", "notes_v1.id"]),
    )


class Invoice(Scoped, Base):
    __tablename__ = "invoices_v1"
    job_id: Mapped[str]
    proposal_id: Mapped[str]
    snapshot: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        branch_fk(),
        record_fk("job_id"),
        ForeignKeyConstraint(
            ["tenant_id", "proposal_id"], ["proposals_v1.tenant_id", "proposals_v1.id"]
        ),
        UniqueConstraint("tenant_id", "proposal_id"),
    )


class Event(Scoped, Base):
    __tablename__ = "events_v1"
    kind: Mapped[str]
    actor: Mapped[str]
    resource_id: Mapped[str]
    evidence: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    __table_args__ = (branch_fk(),)


class Command(Base):
    __tablename__ = "commands_v1"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants_v1.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String, primary_key=True)
    fingerprint: Mapped[str]
    result: Mapped[dict] = mapped_column(JSONB)


class ImportBatch(Scoped, Base):
    __tablename__ = "imports_v1"
    checksum: Mapped[str]
    state: Mapped[str] = mapped_column(String, default="staged")
    rows: Mapped[list] = mapped_column(JSONB)
    report: Mapped[dict] = mapped_column(JSONB, default=dict)
    __table_args__ = (branch_fk(), UniqueConstraint("tenant_id", "branch_id", "checksum"))


class Outbox(Scoped, Base):
    __tablename__ = "outbox_v1"
    channel: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String, default="draft")
    __table_args__ = (branch_fk(),)

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

Trade = Literal["HVAC", "Plumbing", "Electrical"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Customer(Strict):
    primary_property_id: str | None = None
    account_type: Literal["residential", "commercial"] = "residential"
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=80)


class Contact(Customer):
    contact_role: Literal["site", "billing", "both"] = "site"


class Property(Strict):
    address: str = Field(min_length=1, max_length=500)


class Equipment(Strict):
    trade: Trade
    model: str = Field(default="", max_length=200)
    serial: str = Field(default="", max_length=200)


class MaterialNeed(Strict):
    sku_id: str
    quantity: int = Field(gt=0, le=100000)


class Line(Strict):
    description: str = Field(min_length=1, max_length=500)
    kind: Literal["labor", "material", "other"]
    sku_id: str | None = None
    quantity: int = Field(gt=0, le=100000)
    unit_cents: int = Field(ge=0, le=100000000)
    treatment: Literal["billable", "included", "warranty", "fixed_price"] = "billable"
    discount_eligible: bool = False


class Job(Strict):
    trade: Trade
    service: str = Field(min_length=1, max_length=80)
    service_date: date
    customer_approved: bool = False
    billing_mode: Literal["membership", "nonmember", "unknown"] = "unknown"
    required_materials: list[MaterialNeed] = Field(default_factory=list, max_length=100)
    prerequisites: list[str] = Field(default_factory=list, max_length=50)
    lines: list[Line] = Field(default_factory=list, max_length=100)
    currency: Literal["USD"] = "USD"


class SKU(Strict):
    trade: Trade = "Plumbing"
    barcode: str = Field(default="", max_length=150)
    unit: Literal["each"] = "each"
    cost_cents: int = Field(ge=0, default=0)
    price_cents: int = Field(ge=0, default=0)
    image_url: str = Field(default="", max_length=2000)
    image_alt: str = Field(default="", max_length=250)
    image_attribution: str = Field(default="", max_length=1000)
    image_source: str = Field(default="", max_length=2000)
    image_illustrative: bool = True

    @field_validator("image_url", "image_source")
    @classmethod
    def safe_image_url(cls, value):
        from urllib.parse import urlsplit
        import ipaddress
        if not value: return value
        if __import__("re").fullmatch(r"/inventory-images/[A-Za-z0-9_-]+\.(webp|png|jpg|jpeg)", value):
            return value
        url=urlsplit(value)
        if url.scheme!="https" or not url.hostname or url.username or url.password or url.fragment or url.port not in (None,443):
            raise ValueError("Use a public HTTPS image URL.")
        host=url.hostname.lower().rstrip(".")
        if "." not in host or host.endswith((".local",".internal",".localhost")):
            raise ValueError("Use a public HTTPS image URL.")
        try:
            address=ipaddress.ip_address(host)
            if not address.is_global: raise ValueError("Private addresses are not supported.")
        except ValueError as e:
            if str(e)=="Private addresses are not supported.": raise
        return value


class Location(Strict):
    location_type: Literal["warehouse", "truck", "quarantine"]


KINDS = {
    "customers": Customer,
    "contacts": Contact,
    "properties": Property,
    "equipment": Equipment,
    "jobs": Job,
    "skus": SKU,
    "locations": Location,
}


class CreateRecord(Strict):
    branch_id: str
    name: str = Field(min_length=1, max_length=250)
    parent_id: str | None = None
    customer_id: str | None = None
    property_id: str | None = None
    equipment_id: str | None = None
    data: dict = Field(default_factory=dict)


class PatchRecord(Strict):
    expected_revision: int = Field(gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=250)
    data: dict | None = None
    archived: bool | None = None


class NewTerms(Strict):
    starts: date
    ends: date
    discount: int = Field(ge=0, le=100)
    description: str = Field(min_length=1, max_length=4000)
    due_dates: list[date] = Field(default_factory=list, max_length=100)
    grant: int = Field(ge=0, le=10000)

    @model_validator(mode="after")
    def date_order(self):
        if self.starts > self.ends or any(
            not self.starts <= d <= self.ends for d in self.due_dates
        ):
            raise ValueError("Invalid term or due date range.")
        return self


class CreateAgreement(Strict):
    equipment_id: str
    trade: Trade
    service: str = Field(min_length=1, max_length=80)
    terms: NewTerms


class AgreementCommand(Strict):
    action: Literal["preview", "renew", "upgrade", "cancel", "adjust"]
    expected_revision: int = Field(gt=0)
    terms: NewTerms | None = None
    effective_date: date | None = None
    amount: int = Field(default=0, ge=-10000, le=10000)
    reason: str = Field(min_length=1, max_length=1000)


class InventoryCommand(Strict):
    action: Literal[
        "receive",
        "transfer",
        "reserve",
        "release",
        "issue",
        "return",
        "damaged",
        "adjust",
        "threshold",
    ]
    sku_id: str
    location_id: str
    destination_id: str | None = None
    job_id: str | None = None
    reservation_id: str | None = None
    quantity: int = Field(default=0, ge=-100000, le=100000)
    reason: str = Field(min_length=1, max_length=1000)
    minimum: int = Field(default=0, ge=0)
    target: int = Field(default=0, ge=0)


class MaterialEntry(Strict):
    sku_id: str | None
    location_id: str | None
    quantity: int = Field(gt=0, le=100000)
    disposition: Literal["installed", "unused_return", "damaged"]
    source_quote: str = Field(min_length=1, max_length=1000)


class Followup(Strict):
    trade: Trade
    description: str = Field(min_length=1, max_length=1000)
    source_quote: str = Field(min_length=1, max_length=1000)


class Extraction(Strict):
    equipment_id: str | None
    completed_work: str = Field(min_length=1, max_length=4000)
    completed: bool
    materials: list[MaterialEntry] = Field(default_factory=list, max_length=100)
    followups: list[Followup] = Field(default_factory=list, max_length=20)
    unknowns: list[str] = Field(default_factory=list, max_length=50)


class NewProposal(Strict):
    note: str = Field(min_length=1, max_length=12000)
    expected_job_revision: int = Field(gt=0)
    extraction: Extraction | None = None


class Review(Strict):
    action: Literal["approve", "reject", "revise"]
    expected_revision: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)
    extraction: Extraction | None = None
    dismissed_findings: dict[str, str] = Field(default_factory=dict)


class ImportRow(Strict):
    source_id: str = Field(min_length=1, max_length=150)
    kind: Literal[
        "customers",
        "contacts",
        "properties",
        "equipment",
        "jobs",
        "skus",
        "locations",
        "agreements",
        "stock",
    ]
    name: str = Field(min_length=1, max_length=250)
    parent_source: str | None = None
    customer_source: str | None = None
    property_source: str | None = None
    equipment_source: str | None = None
    data: dict
    needs_review: str = Field(default="", max_length=2000)
    resolution: str = Field(default="", max_length=2000)


class ImportRequest(Strict):
    branch_id: str
    rows: list[ImportRow] = Field(min_length=1, max_length=1000)


class MemberRequest(Strict):
    role: Literal["owner", "office", "technician", "viewer"]
    branches: list[str] = Field(min_length=1, max_length=100)
    active: bool = True


class OpeningStock(Strict):
    sku_source: str
    location_source: str
    quantity: int = Field(ge=0, le=100000)

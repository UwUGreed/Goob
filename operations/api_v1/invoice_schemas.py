from datetime import date
from typing import Literal
from pydantic import Field
from operations.api_v1.schemas import Strict, Trade


class InvoiceSelection(Strict):
    customer_id: str
    property_id: str
    job_id: str | None = None
    equipment_id: str | None = None
    trade: Trade = "Plumbing"
    service: Literal["repair", "maintenance"] = "repair"
    service_date: date


class GenerateInvoice(InvoiceSelection):
    source_text: str = Field(min_length=1, max_length=8000)


class InvoiceLine(Strict):
    description: str = Field(min_length=1, max_length=300)
    quantity: str = Field(pattern=r"^\d{1,6}(\.\d{1,3})?$")
    unit_price: str | None = Field(default=None, pattern=r"^-?\d{1,8}(\.\d{1,2})?$")
    category: Literal["labor", "material", "other", "unclassified", "credit"]
    source_text: str = Field(max_length=8000)
    pricebook_id: str | None = None
    apply_membership: bool = False


class InvoiceExtraction(Strict):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(max_length=2000)
    lines: list[InvoiceLine] = Field(min_length=1, max_length=50)
    missing_information: list[str] = Field(max_length=30)
    ambiguities: list[str] = Field(max_length=30)


class InvoiceDraft(InvoiceSelection, InvoiceExtraction):
    source_text: str = Field(default="", max_length=8000)
    generation_source_text: str = Field(default="", max_length=8000)
    invoice_date: date
    due_date: date
    review_note: str = Field(default="", max_length=1000)
    review_confirmed: bool = False


class SaveInvoice(Strict):
    id: str = Field(min_length=1, max_length=80)
    expected_revision: int = Field(default=0, ge=0)
    finalize: bool = False
    preview_token: str | None = None
    draft: InvoiceDraft

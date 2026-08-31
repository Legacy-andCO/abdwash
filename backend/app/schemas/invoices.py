import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class InvoiceLineView(BaseModel):
    description: str
    quantity: int
    unit_price_minor: int
    discount_minor: int
    line_total_minor: int
    vehicle: str | None = None


class RevenueInvoiceView(BaseModel):
    id: uuid.UUID
    invoice_number: str
    document_type: str
    issued_at: datetime
    supply_date: date
    booking_reference: str
    currency_code: str
    supplier: dict[str, object]
    customer: dict[str, object]
    lines: list[InvoiceLineView] = Field(default_factory=list)
    subtotal_minor: int
    discount_minor: int
    vat_amount_minor: int
    total_minor: int
    payment_method: str
    payment_reference: str | None

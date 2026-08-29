import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.public import StrictRequest

InventoryCategory = Literal[
    "chemicals",
    "cleaning_products",
    "microfibers_towels",
    "brushes",
    "pads",
    "bottles_sprayers",
    "ppe",
    "disposable_consumables",
    "equipment_consumables",
    "other",
]
InventoryUnit = Literal[
    "piece", "liter", "milliliter", "kilogram", "gram", "meter", "roll", "box", "pack"
]
LocationType = Literal["main", "mobile_team", "van", "other"]
StockStatus = Literal["normal", "low", "out"]


class InventoryItemCreate(StrictRequest):
    name: str = Field(min_length=1, max_length=160)
    category: InventoryCategory
    code: str | None = Field(default=None, max_length=80)
    unit: InventoryUnit
    default_low_stock_threshold: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=14, decimal_places=3
    )
    notes: str | None = Field(default=None, max_length=4000)


class InventoryItemUpdate(StrictRequest):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    category: InventoryCategory | None = None
    code: str | None = Field(default=None, max_length=80)
    unit: InventoryUnit | None = None
    default_low_stock_threshold: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=3
    )
    notes: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None


class InventoryItemView(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    code: str | None
    unit: str
    is_active: bool
    default_low_stock_threshold: Decimal
    notes: str | None
    total_quantity: Decimal = Decimal("0")
    has_movements: bool = False


class InventoryItemList(BaseModel):
    items: list[InventoryItemView]
    next_offset: int | None


class InventoryLocationCreate(StrictRequest):
    name: str = Field(min_length=1, max_length=160)
    location_type: LocationType
    linked_team_id: uuid.UUID | None = None


class InventoryLocationUpdate(StrictRequest):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    location_type: LocationType | None = None
    linked_team_id: uuid.UUID | None = None
    is_active: bool | None = None


class InventoryLocationView(BaseModel):
    id: uuid.UUID
    name: str
    location_type: str
    linked_team_id: uuid.UUID | None
    linked_team_name: str | None
    is_active: bool
    low_stock_count: int = 0
    out_of_stock_count: int = 0


class StockLine(BaseModel):
    item_id: uuid.UUID
    item_name: str
    code: str | None
    category: str
    unit: str
    location_id: uuid.UUID
    location_name: str
    quantity: Decimal
    threshold: Decimal
    status: StockStatus


class StockList(BaseModel):
    items: list[StockLine]
    next_offset: int | None


class InventoryLocationSummary(BaseModel):
    location_id: uuid.UUID
    location_name: str
    location_type: str
    low_stock_count: int
    out_of_stock_count: int


class InventoryOverview(BaseModel):
    active_item_count: int
    low_stock_count: int
    out_of_stock_count: int
    needs_review_count: int = 0
    locations: list[InventoryLocationSummary]


class InventoryQuantityLine(StrictRequest):
    item_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class InventoryReceiptLine(InventoryQuantityLine):
    unit_cost_minor: int | None = Field(default=None, ge=0)


class InventoryReceiptCreate(StrictRequest):
    location_id: uuid.UUID
    lines: list[InventoryReceiptLine] = Field(min_length=1, max_length=200)
    reference_number: str | None = Field(default=None, max_length=160)
    supplier_name: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)
    opening_balance: bool = False
    record_as_expense: bool = False
    expense_amount_minor: int | None = Field(default=None, gt=0)
    expense_payment_method: str | None = Field(default=None, max_length=40)
    client_event_id: str = Field(min_length=8, max_length=160)

    @model_validator(mode="after")
    def expense_is_complete(self) -> "InventoryReceiptCreate":
        if self.record_as_expense and (
            self.expense_amount_minor is None or not self.expense_payment_method
        ):
            raise ValueError("Expense amount and payment method are required.")
        if not self.record_as_expense and self.expense_amount_minor is not None:
            raise ValueError("Expense amount requires record_as_expense.")
        return self


class InventoryTransferCreate(StrictRequest):
    from_location_id: uuid.UUID
    to_location_id: uuid.UUID
    lines: list[InventoryQuantityLine] = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)
    client_event_id: str = Field(min_length=8, max_length=160)

    @model_validator(mode="after")
    def different_locations(self) -> "InventoryTransferCreate":
        if self.from_location_id == self.to_location_id:
            raise ValueError("Source and destination must be different.")
        return self


class InventoryUsageCreate(StrictRequest):
    location_id: uuid.UUID
    lines: list[InventoryQuantityLine] = Field(min_length=1, max_length=200)
    job_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=4000)
    client_event_id: str = Field(min_length=8, max_length=160)


class InventoryWastageCreate(StrictRequest):
    location_id: uuid.UUID
    lines: list[InventoryQuantityLine] = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=2, max_length=4000)
    client_event_id: str = Field(min_length=8, max_length=160)


class StockCountLine(StrictRequest):
    item_id: uuid.UUID
    counted_quantity: Decimal = Field(ge=0, max_digits=14, decimal_places=3)


class InventoryStockCountCreate(StrictRequest):
    location_id: uuid.UUID
    lines: list[StockCountLine] = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=2, max_length=4000)
    client_event_id: str = Field(min_length=8, max_length=160)


class InventoryThresholdUpdate(StrictRequest):
    low_stock_threshold: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)


class InventoryOperationView(BaseModel):
    id: uuid.UUID
    operation_type: str
    client_event_id: str
    expense_id: uuid.UUID | None
    movement_count: int
    created_at: datetime


class InventoryMovementView(BaseModel):
    id: uuid.UUID
    operation_id: uuid.UUID
    item_id: uuid.UUID
    item_name: str
    unit: str
    movement_type: str
    quantity: Decimal
    signed_quantity: Decimal
    location_id: uuid.UUID
    location_name: str
    from_location_id: uuid.UUID | None
    from_location_name: str | None
    to_location_id: uuid.UUID | None
    to_location_name: str | None
    job_id: uuid.UUID | None
    booking_reference: str | None
    expense_id: uuid.UUID | None
    actor_staff_id: uuid.UUID
    actor_name: str
    reason: str | None
    reference_number: str | None
    created_at: datetime


class InventoryMovementList(BaseModel):
    items: list[InventoryMovementView]
    next_offset: int | None


class InventoryQuantityReportRow(BaseModel):
    item_id: uuid.UUID
    item_name: str
    unit: str
    quantity: Decimal


class InventoryUsageReport(BaseModel):
    start_at: datetime
    end_at: datetime
    usage: list[InventoryQuantityReportRow]
    wastage: list[InventoryQuantityReportRow]


class TeamStockSummary(BaseModel):
    team_id: uuid.UUID
    location_id: uuid.UUID | None
    location_name: str | None
    item_count: int
    low_stock_count: int
    out_of_stock_count: int
    items: list[StockLine]


class ServiceConsumptionLine(StrictRequest):
    item_id: uuid.UUID
    expected_quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class ServiceConsumptionTemplateUpdate(StrictRequest):
    lines: list[ServiceConsumptionLine] = Field(max_length=200)


class ServiceConsumptionTemplateLine(BaseModel):
    item_id: uuid.UUID
    item_name: str
    unit: str
    expected_quantity: Decimal


class JobConsumptionLineView(BaseModel):
    id: uuid.UUID
    booking_service_id: uuid.UUID
    service_id: uuid.UUID | None
    service_name: str
    item_id: uuid.UUID | None
    item_name: str
    unit: str
    expected_quantity: Decimal
    automatic_applied_quantity: Decimal
    preexisting_manual_quantity: Decimal
    additional_manual_quantity: Decimal = Decimal("0")
    shortfall_quantity: Decimal
    issue_code: str | None


class JobConsumptionSummary(BaseModel):
    id: uuid.UUID
    status: str
    source_location_id: uuid.UUID | None
    source_location_name: str | None
    source_resolution: str
    issue_code: str | None
    processed_at: datetime
    expected_lines: int
    attention_lines: int
    has_attention: bool
    reviewed_at: datetime | None
    review_note: str | None
    lines: list[JobConsumptionLineView]


class InventoryAttentionItem(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    booking_reference: str
    customer_name: str
    source_location_name: str | None
    issue_code: str | None
    processed_at: datetime
    attention_lines: int


class InventoryAttentionList(BaseModel):
    items: list[InventoryAttentionItem]
    next_offset: int | None


class InventoryConsumptionReview(StrictRequest):
    note: str | None = Field(default=None, max_length=4000)

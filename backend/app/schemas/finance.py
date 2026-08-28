import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.public import StrictRequest

ExpenseCategory = Literal[
    "chemicals_supplies",
    "fuel",
    "vehicle_transport",
    "equipment",
    "maintenance_repairs",
    "staff",
    "marketing",
    "rent_utilities",
    "software_subscriptions",
    "government_fees",
    "professional_services",
    "miscellaneous",
]


class ExpenseCreate(StrictRequest):
    expense_date: date
    category: ExpenseCategory
    description: str = Field(min_length=1, max_length=500)
    amount_minor: int = Field(gt=0)
    payment_method: str = Field(min_length=1, max_length=40)
    paid_by_staff_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    related_job_id: uuid.UUID | None = None
    supplier_name: str | None = Field(default=None, max_length=200)
    reference_number: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=4000)
    client_event_id: str = Field(min_length=8, max_length=160)


class ExpenseVoid(StrictRequest):
    reason: str = Field(min_length=2, max_length=4000)


class ExpenseView(BaseModel):
    id: uuid.UUID
    expense_date: date
    category: str
    description: str
    amount_minor: int
    currency_code: str
    payment_method: str
    paid_by_staff_id: uuid.UUID | None
    paid_by_staff_name: str | None
    team_id: uuid.UUID | None
    team_name: str | None
    related_job_id: uuid.UUID | None
    related_booking_reference: str | None
    supplier_name: str | None
    reference_number: str | None
    notes: str | None
    receipt_available: bool
    status: str
    created_by_staff_id: uuid.UUID
    created_at: datetime
    voided_at: datetime | None
    void_reason: str | None


class ExpenseCategoryTotal(BaseModel):
    category: str
    amount_minor: int
    percentage: float


class ExpenseList(BaseModel):
    items: list[ExpenseView]
    next_cursor: str | None
    total_expenses_minor: int
    category_totals: list[ExpenseCategoryTotal]
    currency_code: str


class CashPendingPayment(BaseModel):
    payment_transaction_id: uuid.UUID
    booking_reference: str
    job_id: uuid.UUID
    amount_minor: int
    currency_code: str
    collected_at: datetime


class CashPendingStaff(BaseModel):
    staff_id: uuid.UUID
    staff_name: str
    payment_count: int
    expected_cash_minor: int
    currency_code: str
    oldest_unreconciled_at: datetime


class CashPendingList(BaseModel):
    items: list[CashPendingStaff]


class CashPendingDetail(BaseModel):
    staff_id: uuid.UUID
    staff_name: str
    expected_cash_minor: int
    currency_code: str
    payments: list[CashPendingPayment]


class CashReconciliationCreate(StrictRequest):
    staff_id: uuid.UUID
    payment_transaction_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    declared_cash_minor: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=4000)
    client_event_id: str = Field(min_length=8, max_length=160)

    @model_validator(mode="after")
    def unique_payments(self) -> "CashReconciliationCreate":
        if len(set(self.payment_transaction_ids)) != len(self.payment_transaction_ids):
            raise ValueError("Payment transaction IDs must be unique.")
        return self


class CashReconciliationVoid(StrictRequest):
    reason: str = Field(min_length=2, max_length=4000)


class CashReconciliationView(BaseModel):
    id: uuid.UUID
    staff_id: uuid.UUID
    staff_name: str
    team_id: uuid.UUID | None
    team_name: str | None
    period_start: datetime
    period_end: datetime
    expected_cash_minor: int
    declared_cash_minor: int
    difference_minor: int
    difference_label: Literal["exact", "short", "over"]
    currency_code: str
    status: str
    note: str | None
    payment_count: int
    payments: list[CashPendingPayment]
    created_by_staff_id: uuid.UUID
    confirmed_at: datetime
    voided_at: datetime | None
    void_reason: str | None


class CashReconciliationList(BaseModel):
    items: list[CashReconciliationView]
    next_cursor: str | None


class FinanceSeriesPoint(BaseModel):
    date: date
    collected_revenue_minor: int
    expenses_minor: int
    operational_profit_minor: int


class TeamContribution(BaseModel):
    team_id: uuid.UUID
    team_name: str
    collected_revenue_minor: int
    completed_jobs: int
    direct_expenses_minor: int
    direct_contribution_minor: int


class FinanceOverview(BaseModel):
    start_date: date
    end_date: date
    currency_code: str
    booked_sales_minor: int
    collected_revenue_minor: int
    outstanding_minor: int
    expenses_minor: int
    operational_profit_minor: int
    margin_percent: float
    cash_pending_minor: int
    cash_short_over_minor: int
    expense_categories: list[ExpenseCategoryTotal]
    series: list[FinanceSeriesPoint]
    team_contributions: list[TeamContribution]


class PersonalCashSummary(BaseModel):
    date: date
    currency_code: str
    collected_today_minor: int
    awaiting_handover_minor: int

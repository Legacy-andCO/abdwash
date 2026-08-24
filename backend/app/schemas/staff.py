import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.public import StrictRequest


class StaffVehicle(BaseModel):
    make: str
    model: str
    year: int | None
    vehicle_type: str
    colour: str | None
    plate_number: str | None
    notes: str | None
    service_name: str
    amount_minor: int


class StaffJob(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    booking_reference: str
    assigned_staff_id: uuid.UUID | None
    assigned_staff_name: str | None
    status: str
    scheduled_start: datetime
    scheduled_end: datetime
    en_route_at: datetime | None
    estimated_arrival_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    customer_name: str
    customer_phone: str
    written_address: str
    location_url: str
    latitude: float | None
    longitude: float | None
    location_instructions: str | None
    payment_status: str
    payment_method: str | None
    total_amount_minor: int
    currency_code: str
    vehicles: list[StaffVehicle]


class StaffJobList(BaseModel):
    jobs: list[StaffJob]
    next_offset: int | None


class Coordinates(StrictRequest):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class JobAction(StrictRequest):
    client_event_id: str = Field(min_length=8, max_length=160)
    client_timestamp: datetime | None = None


class StartTripAction(JobAction):
    origin: Coordinates


class AssignmentAction(JobAction):
    staff_id: uuid.UUID
    expected_version: int | None = Field(default=None, ge=1)
    confirm_active_reassignment: bool = False


class StaffMember(BaseModel):
    id: uuid.UUID
    display_name: str
    role: str
    assigned_jobs_today: int
    current_job_reference: str | None
    current_job_status: str | None


class CancellationReview(JobAction):
    decision: str = Field(pattern="^(approved|rejected)$")
    review_note: str | None = Field(default=None, max_length=2000)


class CancellationItem(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    booking_reference: str
    customer_name: str
    reason: str | None
    requested_at: datetime
    scheduled_start: datetime
    payment_status: str
    status: str


class ReportSummary(BaseModel):
    start_date: date
    end_date: date
    bookings: int
    completed_washes: int
    booked_sales_minor: int
    collected_revenue_minor: int
    outstanding_minor: int
    average_booking_value_minor: int
    currency_code: str

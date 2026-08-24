import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.public import BookingVehicleSummary, StrictRequest


class CustomerProfileResponse(BaseModel):
    id: uuid.UUID
    first_name: str
    surname: str
    email: str
    phone: str


class CustomerContextResponse(BaseModel):
    profile: CustomerProfileResponse | None
    booking_count: int


class CustomerBookingStatus(BaseModel):
    key: str
    label: str
    stage: int
    job_status: str | None


class CustomerBookingSummary(BaseModel):
    id: uuid.UUID
    reference: str
    status: CustomerBookingStatus
    payment_status: str
    scheduled_start: datetime
    scheduled_end: datetime
    vehicle_count: int
    total_amount_minor: int
    currency_code: str
    written_address: str
    vehicles: list[BookingVehicleSummary]
    created_at: datetime
    cancellation_eligible: bool
    reschedule_eligible: bool
    estimated_arrival_at: datetime | None = None
    category: str


class CustomerBookingListResponse(BaseModel):
    bookings: list[CustomerBookingSummary]


class CustomerBookingDetail(CustomerBookingSummary):
    payment_choice: str
    payment_status: str
    location_url: str
    location_instructions: str | None
    latitude: float | None
    longitude: float | None
    cancellation_cutoff_at: datetime
    cancellation_status: str | None
    timezone: str


class CustomerBookingActionResponse(BaseModel):
    booking: CustomerBookingDetail


class CustomerCancellationCreate(StrictRequest):
    reason: str | None = Field(default=None, max_length=2000)


class CustomerRescheduleCreate(StrictRequest):
    hold_token: Annotated[str, StringConstraints(min_length=32, max_length=255)]

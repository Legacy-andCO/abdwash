import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.domain.locations import is_supported_google_maps_url
from app.domain.phones import normalize_phone_number

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SafeBusinessSettings(BaseModel):
    timezone: str
    currency_code: str
    opening_time: time
    closing_time: time
    slot_duration_minutes: int
    multi_vehicle_threshold: int
    multi_vehicle_required_slots: int
    hold_duration_minutes: int
    cancellation_cutoff_hours: int
    mobile_minimum_enabled: bool = False
    mobile_minimum_minor: int = 0


class ServicePricePublic(BaseModel):
    vehicle_type: str
    price_minor: int


class ServiceAddonPublic(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    price_minor: int
    currency_code: str
    default_duration_minutes: int
    mobile_available: bool
    shop_available: bool


class ServicePublic(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    price_minor: int
    currency_code: str
    estimated_duration_minutes: int
    mobile_available: bool = True
    shop_available: bool = True
    included_features: list[str] = Field(default_factory=list)
    product_kind: str = "single_service"
    customer_bookable: bool = True
    prices: list[ServicePricePublic] = Field(default_factory=list)
    addons: list[ServiceAddonPublic] = Field(default_factory=list)


class CatalogueResponse(BaseModel):
    business_name: str
    settings: SafeBusinessSettings
    services: list[ServicePublic]


class AvailabilitySlot(BaseModel):
    time: time
    starts_at: datetime
    ends_at: datetime
    available: bool
    required_slot_count: int
    unavailable_reason: str | None = None


class AvailabilityResponse(BaseModel):
    date: date
    timezone: str
    vehicle_count: int
    required_slot_count: int
    slots: list[AvailabilitySlot]


class HoldCreate(StrictRequest):
    date: date
    start_time: time
    vehicle_count: int = Field(ge=1, le=20)
    service_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    addon_ids: list[uuid.UUID] = Field(default_factory=list, max_length=400)


class HoldResponse(BaseModel):
    hold_token: str
    starts_at: datetime
    ends_at: datetime
    expires_at: datetime
    required_slot_count: int


class CustomerContact(StrictRequest):
    first_name: NonBlank = Field(max_length=100)
    surname: NonBlank = Field(max_length=100)
    email: EmailStr | None = None
    phone: NonBlank = Field(max_length=40)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_optional_email(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: object) -> str:
        return normalize_phone_number(value)


class BookingLocation(StrictRequest):
    written_address: NonBlank = Field(max_length=2000)
    location_url: HttpUrl
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    instructions: NonBlank = Field(max_length=2000)

    @field_validator("location_url")
    @classmethod
    def require_google_maps_url(cls, value: HttpUrl) -> HttpUrl:
        if not is_supported_google_maps_url(str(value)):
            raise ValueError("Use a supported Google Maps link.")
        return value

    @model_validator(mode="after")
    def coordinates_together(self) -> "BookingLocation":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class BookingVehicleCreate(StrictRequest):
    vehicle_id: uuid.UUID | None = None
    make: NonBlank = Field(max_length=100)
    model: NonBlank = Field(max_length=100)
    year: int | None = Field(default=None, ge=1900, le=2200)
    vehicle_type: NonBlank = Field(max_length=80)
    colour: str | None = Field(default=None, max_length=80)
    plate_number: NonBlank = Field(max_length=40)
    notes: str | None = Field(default=None, max_length=2000)
    service_id: uuid.UUID
    addon_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    loyalty_reward_id: uuid.UUID | None = None

    @field_validator("addon_ids")
    @classmethod
    def unique_addons(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(value)) != len(value):
            raise ValueError("Each add-on can be selected only once.")
        return value


class BookingBillingDetails(StrictRequest):
    company_name: NonBlank = Field(max_length=200)
    billing_address: NonBlank = Field(max_length=2000)
    tax_registration_number: str | None = Field(default=None, max_length=40)


class BookingAddonSummary(BaseModel):
    id: uuid.UUID | None = None
    name: str
    price_minor: int
    expected_duration_minutes: int


class BookingCreate(StrictRequest):
    hold_token: Annotated[str, StringConstraints(min_length=32, max_length=255)]
    contact: CustomerContact
    location: BookingLocation
    vehicles: list[BookingVehicleCreate] = Field(min_length=1, max_length=20)
    payment_choice: Literal["pay_now", "pay_after_service"]
    billing: BookingBillingDetails | None = None
    source: Literal["web", "mobile", "admin"] = "web"


class BookingVehicleSummary(BaseModel):
    make: str
    model: str
    year: int | None
    vehicle_type: str
    colour: str | None
    plate_number: str | None
    service_name: str
    service_id: uuid.UUID | None = None
    line_total_minor: int
    list_price_minor: int | None = None
    discount_minor: int = 0
    discount_type: str | None = None
    loyalty_reward_id: uuid.UUID | None = None
    expected_duration_minutes: int | None = None
    addons: list[BookingAddonSummary] = Field(default_factory=list)


class BookingResponse(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID | None = Field(default=None, exclude=True)
    reference: str
    status: str
    payment_choice: str
    payment_status: str
    scheduled_start: datetime
    scheduled_end: datetime
    vehicle_count: int
    total_amount_minor: int
    currency_code: str
    customer_first_name: str
    customer_surname: str
    written_address: str
    location_url: str
    location_instructions: str | None
    vehicles: list[BookingVehicleSummary]
    management_token: str


class BookingManagementResponse(BaseModel):
    reference: str
    status: str
    payment_choice: str
    payment_status: str
    scheduled_start: datetime
    scheduled_end: datetime
    total_amount_minor: int
    currency_code: str
    customer_first_name: str
    customer_surname: str
    written_address: str
    location_url: str
    location_instructions: str | None
    vehicles: list[BookingVehicleSummary]
    cancellation_eligible: bool
    cancellation_cutoff_at: datetime
    cancellation_status: str | None
    timezone: str


class CancellationRequestCreate(StrictRequest):
    reason: str | None = Field(default=None, max_length=2000)


class CancellationRequestResponse(BaseModel):
    id: uuid.UUID
    status: str
    booking: BookingManagementResponse


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: dict[str, object] = Field(default_factory=dict)

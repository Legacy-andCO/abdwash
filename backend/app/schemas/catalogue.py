import uuid
from datetime import time
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.public import StrictRequest

VehicleType = Literal["sedan", "suv", "hatchback", "coupe", "pickup", "van", "other"]


class VehiclePriceInput(StrictRequest):
    vehicle_type: VehicleType
    price_minor: int = Field(ge=0)


class VehiclePriceView(BaseModel):
    vehicle_type: str
    price_minor: int


class AddonInput(StrictRequest):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    price_minor: int = Field(ge=0)
    default_duration_minutes: int = Field(default=0, ge=0, le=1440)
    mobile_available: bool = True
    shop_available: bool = True
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10_000)

    @model_validator(mode="after")
    def channel_required(self) -> "AddonInput":
        if not self.mobile_available and not self.shop_available:
            raise ValueError("Select Mobile, Shop, or both.")
        return self


class AddonPatch(StrictRequest):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    price_minor: int | None = Field(default=None, ge=0)
    default_duration_minutes: int | None = Field(default=None, ge=0, le=1440)
    mobile_available: bool | None = None
    shop_available: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)

    @model_validator(mode="after")
    def nonnullable_updates(self) -> "AddonPatch":
        nullable = {"description"}
        invalid = {
            field
            for field in self.model_fields_set - nullable
            if getattr(self, field) is None
        }
        if invalid:
            raise ValueError("Catalogue fields cannot be null; omit unchanged fields.")
        return self


class AddonView(BaseModel):
    id: uuid.UUID
    service_id: uuid.UUID
    name: str
    description: str | None
    price_minor: int
    default_duration_minutes: int
    mobile_available: bool
    shop_available: bool
    is_active: bool
    sort_order: int


class ServiceInput(StrictRequest):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    default_duration_minutes: int = Field(ge=15, le=1440)
    mobile_available: bool = True
    shop_available: bool = True
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10_000)
    prices: list[VehiclePriceInput] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def valid_configuration(self) -> "ServiceInput":
        if not self.mobile_available and not self.shop_available:
            raise ValueError("Select Mobile, Shop, or both.")
        types = [price.vehicle_type for price in self.prices]
        if len(types) != len(set(types)):
            raise ValueError("Each vehicle type can have only one price.")
        return self


class ServicePatch(StrictRequest):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    default_duration_minutes: int | None = Field(default=None, ge=15, le=1440)
    mobile_available: bool | None = None
    shop_available: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    prices: list[VehiclePriceInput] | None = Field(default=None, min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_prices(self) -> "ServicePatch":
        nullable = {"description"}
        invalid = {
            field
            for field in self.model_fields_set - nullable
            if getattr(self, field) is None
        }
        if invalid:
            raise ValueError("Catalogue fields cannot be null; omit unchanged fields.")
        if self.prices is not None:
            types = [price.vehicle_type for price in self.prices]
            if len(types) != len(set(types)):
                raise ValueError("Each vehicle type can have only one price.")
        return self


class ServiceManagementView(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    default_duration_minutes: int
    mobile_available: bool
    shop_available: bool
    is_active: bool
    sort_order: int
    prices: list[VehiclePriceView]
    addons: list[AddonView]


class CatalogueManagementView(BaseModel):
    currency_code: str
    vehicle_types: list[str]
    services: list[ServiceManagementView]


class OperatingHourInput(StrictRequest):
    weekday: int = Field(ge=0, le=6)
    is_open: bool
    opening_time: time | None = None
    closing_time: time | None = None

    @model_validator(mode="after")
    def valid_window(self) -> "OperatingHourInput":
        if self.is_open and (
            self.opening_time is None
            or self.closing_time is None
            or self.closing_time <= self.opening_time
        ):
            raise ValueError("Open days require a valid opening and closing time.")
        return self


class OperatingHourView(BaseModel):
    weekday: int
    is_open: bool
    opening_time: time | None
    closing_time: time | None


class BusinessBookingSettingsPatch(StrictRequest):
    slot_duration_minutes: Literal[60, 90, 120] | None = None
    cancellation_cutoff_hours: int | None = Field(default=None, ge=0, le=720)
    mobile_minimum_enabled: bool | None = None
    mobile_minimum_minor: int | None = Field(default=None, ge=0)
    default_team_turnaround_minutes: int | None = Field(default=None, ge=0, le=480)
    loyalty_reward_service_id: uuid.UUID | None = None
    operating_hours: list[OperatingHourInput] | None = Field(
        default=None, min_length=7, max_length=7
    )

    @model_validator(mode="after")
    def weekdays_unique(self) -> "BusinessBookingSettingsPatch":
        nullable = {"loyalty_reward_service_id"}
        invalid = {
            field
            for field in self.model_fields_set - nullable
            if getattr(self, field) is None
        }
        if invalid:
            raise ValueError("Business settings cannot be null; omit unchanged fields.")
        if self.operating_hours is not None:
            weekdays = [item.weekday for item in self.operating_hours]
            if set(weekdays) != set(range(7)):
                raise ValueError("Provide each weekday exactly once.")
        return self


class BusinessBookingSettingsView(BaseModel):
    currency_code: str
    slot_duration_minutes: int
    cancellation_cutoff_hours: int
    mobile_minimum_enabled: bool
    mobile_minimum_minor: int
    default_team_turnaround_minutes: int
    loyalty_reward_service_id: uuid.UUID | None
    operating_hours: list[OperatingHourView]

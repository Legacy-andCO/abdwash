import pytest
from pydantic import ValidationError

from app.schemas.customer import (
    CustomerAddressWrite,
    CustomerProfileUpdate,
    CustomerVehicleResponse,
    CustomerVehicleWrite,
)


def test_profile_phone_is_normalized_to_e164() -> None:
    profile = CustomerProfileUpdate(first_name="Noor", surname="Ali", phone="050 123 4567")
    assert profile.phone == "+971501234567"


def test_profile_rejects_impossible_phone() -> None:
    with pytest.raises(ValidationError):
        CustomerProfileUpdate(first_name="Noor", surname="Ali", phone="123")


def test_profile_patch_has_no_email_field() -> None:
    with pytest.raises(ValidationError):
        CustomerProfileUpdate(
            first_name="Noor",
            surname="Ali",
            phone="+971501234567",
            email="attacker@example.com",  # type: ignore[call-arg]
        )


def test_saved_location_reuses_strict_maps_validation() -> None:
    address = CustomerAddressWrite(
        label="Home",
        written_address="Al Reem Island, Abu Dhabi",
        location_url="https://www.google.com/maps/search/?api=1&query=24.49%2C54.40",
        latitude=24.49,
        longitude=54.40,
        instructions="Gate 2",
        is_default=True,
    )
    assert address.is_default is True


def test_saved_location_rejects_generic_url() -> None:
    with pytest.raises(ValidationError):
        CustomerAddressWrite(
            label="Home",
            written_address="Al Reem Island, Abu Dhabi",
            location_url="https://example.com/location",
        )


def test_new_or_edited_saved_vehicle_requires_plate() -> None:
    with pytest.raises(ValidationError):
        CustomerVehicleWrite(
            make="Toyota",
            model="Camry",
            vehicle_type="sedan",
            plate_number="",
        )


def test_legacy_saved_vehicle_without_plate_remains_readable() -> None:
    vehicle = CustomerVehicleResponse(
        id="e4742df1-0f88-4b73-b39d-48efdb0c553a",
        make="Toyota",
        model="Camry",
        year=None,
        vehicle_type="sedan",
        colour=None,
        plate_number=None,
        notes=None,
    )
    assert vehicle.plate_number is None

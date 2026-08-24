import pytest
from pydantic import ValidationError

from app.schemas.customer import CustomerAddressWrite, CustomerProfileUpdate


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

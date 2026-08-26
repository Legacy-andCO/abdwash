import uuid

import pytest
from pydantic import ValidationError

from app.schemas.public import BookingCreate
from app.services.idempotency import canonical_request_hash


def valid_booking_payload() -> dict[str, object]:
    return {
        "hold_token": "a" * 40,
        "contact": {
            "first_name": "Amina",
            "surname": "Khan",
            "email": "amina@example.com",
            "phone": "+971500000000",
        },
        "location": {
            "written_address": "Dubai Marina",
            "location_url": "https://maps.google.com/?q=Dubai",
            "instructions": "Meet at the main entrance",
        },
        "vehicles": [
            {
                "make": "Toyota",
                "model": "Camry",
                "vehicle_type": "sedan",
                "plate_number": "A 12345",
                "service_id": str(uuid.uuid4()),
            }
        ],
        "payment_choice": "pay_after_service",
    }


def test_public_booking_rejects_server_controlled_fields() -> None:
    payload = valid_booking_payload()
    payload.update({"total_amount_minor": 1, "payment_status": "paid", "status": "completed"})
    with pytest.raises(ValidationError):
        BookingCreate.model_validate(payload)


def test_payment_choice_is_bounded() -> None:
    payload = valid_booking_payload()
    payload["payment_choice"] = "paid"
    with pytest.raises(ValidationError):
        BookingCreate.model_validate(payload)


def test_coordinates_must_be_paired() -> None:
    payload = valid_booking_payload()
    payload["location"]["latitude"] = 25.08  # type: ignore[index]
    with pytest.raises(ValidationError, match="provided together"):
        BookingCreate.model_validate(payload)


@pytest.mark.parametrize(
    ("path", "value"),
    [(("location", "instructions"), " "), (("vehicles", 0, "plate_number"), "")],
)
def test_booking_requires_location_notes_and_vehicle_plate(
    path: tuple[object, ...], value: str
) -> None:
    payload = valid_booking_payload()
    target: object = payload
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]
    with pytest.raises(ValidationError):
        BookingCreate.model_validate(payload)


@pytest.mark.parametrize(
    "path",
    [("location", "instructions"), ("vehicles", 0, "plate_number")],
)
def test_booking_rejects_missing_location_notes_and_vehicle_plate(
    path: tuple[object, ...],
) -> None:
    payload = valid_booking_payload()
    target: object = payload
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    del target[path[-1]]  # type: ignore[index]
    with pytest.raises(ValidationError):
        BookingCreate.model_validate(payload)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("050 123 4567", "+971501234567"),
        ("+971 50 123 4567", "+971501234567"),
        ("050-123-4567", "+971501234567"),
        ("+44 20 7946 0958", "+442079460958"),
    ],
)
def test_phone_numbers_are_validated_and_normalized(value: str, expected: str) -> None:
    payload = valid_booking_payload()
    payload["contact"]["phone"] = value  # type: ignore[index]
    request = BookingCreate.model_validate(payload)
    assert request.contact.phone == expected


@pytest.mark.parametrize("value", ["not-a-number", "123", "+971 1 2"])
def test_invalid_phone_numbers_are_rejected(value: str) -> None:
    payload = valid_booking_payload()
    payload["contact"]["phone"] = value  # type: ignore[index]
    with pytest.raises(ValidationError, match="valid international phone"):
        BookingCreate.model_validate(payload)


@pytest.mark.parametrize(
    "value",
    [
        "https://google.com/maps/place/Yas+Acres",
        "https://www.google.com/maps/search/?api=1&query=24.4%2C54.6",
        "https://maps.google.com/?q=Dubai",
        "https://maps.app.goo.gl/AbCd1234",
    ],
)
def test_supported_google_maps_links_are_accepted(value: str) -> None:
    payload = valid_booking_payload()
    payload["location"]["location_url"] = value  # type: ignore[index]
    BookingCreate.model_validate(payload)


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com/maps/Yas",
        "https://google.com.attacker.com/maps/Yas",
        "http://www.google.com/maps/Yas",
    ],
)
def test_non_google_or_deceptive_map_links_are_rejected(value: str) -> None:
    payload = valid_booking_payload()
    payload["location"]["location_url"] = value  # type: ignore[index]
    with pytest.raises(ValidationError, match="supported Google Maps"):
        BookingCreate.model_validate(payload)


def test_valid_coordinates_and_generated_url_are_accepted() -> None:
    payload = valid_booking_payload()
    payload["location"].update(  # type: ignore[union-attr]
        {
            "latitude": 24.4539,
            "longitude": 54.3773,
            "location_url": (
                "https://www.google.com/maps/search/?api=1&query=24.4539%2C54.3773"
            ),
        }
    )
    request = BookingCreate.model_validate(payload)
    assert request.location.latitude == 24.4539
    assert request.location.longitude == 54.3773


@pytest.mark.parametrize(
    ("field", "value"),
    [("latitude", 90.1), ("latitude", -90.1), ("longitude", 180.1), ("longitude", -180.1)],
)
def test_coordinate_bounds_are_enforced(field: str, value: float) -> None:
    payload = valid_booking_payload()
    payload["location"].update(  # type: ignore[union-attr]
        {"latitude": 24.4539, "longitude": 54.3773, field: value}
    )
    with pytest.raises(ValidationError):
        BookingCreate.model_validate(payload)


def test_request_hash_is_order_independent_and_payload_sensitive() -> None:
    left = {"a": 1, "b": {"c": 2}}
    right = {"b": {"c": 2}, "a": 1}
    assert canonical_request_hash(left) == canonical_request_hash(right)
    assert canonical_request_hash(left) != canonical_request_hash({"a": 2, "b": {"c": 2}})

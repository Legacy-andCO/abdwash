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
        },
        "vehicles": [
            {
                "make": "Toyota",
                "model": "Camry",
                "vehicle_type": "sedan",
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


def test_request_hash_is_order_independent_and_payload_sensitive() -> None:
    left = {"a": 1, "b": {"c": 2}}
    right = {"b": {"c": 2}, "a": 1}
    assert canonical_request_hash(left) == canonical_request_hash(right)
    assert canonical_request_hash(left) != canonical_request_hash({"a": 2, "b": {"c": 2}})

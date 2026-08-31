import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.schemas.public import CustomerContact
from app.services.customer_communications import queue_customer_email_if_available


@pytest.mark.parametrize("value", [None, "", "   "])
def test_booking_contact_accepts_missing_or_blank_email(value: str | None) -> None:
    payload: dict[str, object] = {
        "first_name": "Amina",
        "surname": "Ali",
        "phone": "+971501234567",
    }
    if value is not None:
        payload["email"] = value
    contact = CustomerContact.model_validate(payload)
    assert contact.email is None


def test_booking_contact_rejects_invalid_non_empty_email() -> None:
    with pytest.raises(ValidationError):
        CustomerContact(
            first_name="Amina",
            surname="Ali",
            phone="+971501234567",
            email="not-an-email",
        )


def test_customer_email_queue_skips_null_and_blank_recipients() -> None:
    session = MagicMock()
    common = {
        "business_id": uuid.uuid4(),
        "booking_id": uuid.uuid4(),
        "notification_type": "booking_confirmed",
        "dedupe_key": "booking-confirmed:test",
        "payload": {"booking_reference": "TRI-TEST"},
        "next_attempt_at": datetime.now(UTC),
    }
    assert queue_customer_email_if_available(session, recipient=None, **common) is None
    assert queue_customer_email_if_available(session, recipient="  ", **common) is None
    session.add.assert_not_called()


def test_customer_email_queue_preserves_valid_email_behavior() -> None:
    session = MagicMock()
    record = queue_customer_email_if_available(
        session,
        business_id=uuid.uuid4(),
        booking_id=uuid.uuid4(),
        notification_type="booking_confirmed",
        dedupe_key="booking-confirmed:test",
        recipient=" customer@example.com ",
        payload={"booking_reference": "TRI-TEST"},
        next_attempt_at=datetime.now(UTC),
    )
    assert record is not None
    assert record.recipient == "customer@example.com"
    session.add.assert_called_once_with(record)

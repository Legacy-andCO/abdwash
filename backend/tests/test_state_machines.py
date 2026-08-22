import pytest

from app.domain.enums import BookingStatus, JobStatus, PaymentStatus
from app.domain.errors import ConflictError
from app.domain.state_machines import (
    BOOKING_TRANSITIONS,
    JOB_TRANSITIONS,
    PAYMENT_TRANSITIONS,
    validate_transition,
)


def test_valid_job_transition() -> None:
    validate_transition(JobStatus.ASSIGNED, JobStatus.IN_PROGRESS, JOB_TRANSITIONS)


def test_completed_job_cannot_restart() -> None:
    with pytest.raises(ConflictError, match="Cannot transition"):
        validate_transition(JobStatus.COMPLETED, JobStatus.IN_PROGRESS, JOB_TRANSITIONS)


def test_cancelled_booking_is_terminal() -> None:
    with pytest.raises(ConflictError):
        validate_transition(BookingStatus.CANCELLED, BookingStatus.CONFIRMED, BOOKING_TRANSITIONS)


def test_paid_payment_must_enter_refund_workflow() -> None:
    with pytest.raises(ConflictError):
        validate_transition(PaymentStatus.PAID, PaymentStatus.REFUNDED, PAYMENT_TRANSITIONS)


def test_same_state_is_idempotent() -> None:
    validate_transition(JobStatus.COMPLETED, JobStatus.COMPLETED, JOB_TRANSITIONS)

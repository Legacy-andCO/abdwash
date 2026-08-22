from app.domain.enums import BookingStatus, JobStatus, PaymentStatus
from app.domain.errors import ConflictError

BOOKING_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.PENDING_PAYMENT: {BookingStatus.CONFIRMED, BookingStatus.CANCELLED},
    BookingStatus.CONFIRMED: {
        BookingStatus.CANCELLATION_REQUESTED,
        BookingStatus.COMPLETED,
    },
    BookingStatus.CANCELLATION_REQUESTED: {BookingStatus.CONFIRMED, BookingStatus.CANCELLED},
    BookingStatus.CANCELLED: set(),
    BookingStatus.COMPLETED: set(),
}

JOB_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.UNASSIGNED: {JobStatus.ASSIGNED, JobStatus.CANCELLED},
    JobStatus.ASSIGNED: {JobStatus.UNASSIGNED, JobStatus.IN_PROGRESS, JobStatus.CANCELLED},
    JobStatus.IN_PROGRESS: {JobStatus.COMPLETED, JobStatus.CANCELLED},
    JobStatus.COMPLETED: set(),
    JobStatus.CANCELLED: set(),
}

PAYMENT_TRANSITIONS: dict[PaymentStatus, set[PaymentStatus]] = {
    PaymentStatus.UNPAID: {PaymentStatus.PENDING, PaymentStatus.PAID},
    PaymentStatus.PENDING: {PaymentStatus.PAID, PaymentStatus.FAILED},
    PaymentStatus.PAID: {PaymentStatus.REFUND_PENDING},
    PaymentStatus.FAILED: {PaymentStatus.PENDING},
    PaymentStatus.REFUND_PENDING: {PaymentStatus.REFUNDED, PaymentStatus.PAID},
    PaymentStatus.REFUNDED: set(),
}


def validate_transition(
    current: object, target: object, transitions: dict[object, set[object]]
) -> None:
    if target == current:
        return
    if target not in transitions.get(current, set()):
        raise ConflictError(
            "INVALID_STATE_TRANSITION", f"Cannot transition from {current} to {target}."
        )

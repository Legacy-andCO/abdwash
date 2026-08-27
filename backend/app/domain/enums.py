from enum import StrEnum


class BookingStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    CONFIRMED = "confirmed"
    CANCELLATION_REQUESTED = "cancellation_requested"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class JobStatus(StrEnum):
    UNASSIGNED = "unassigned"
    ASSIGNED = "assigned"
    EN_ROUTE = "en_route"
    ARRIVED = "arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentStatus(StrEnum):
    UNPAID = "unpaid"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"


class PaymentChoice(StrEnum):
    PAY_NOW = "pay_now"
    PAY_AFTER_SERVICE = "pay_after_service"


class StaffRole(StrEnum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    ADMIN = "admin"


class LeaveStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class CancellationStatus(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"


class SlotStatus(StrEnum):
    FREE = "free"
    HELD = "held"
    RESERVED = "reserved"
    BLOCKED = "blocked"


class HoldStatus(StrEnum):
    ACTIVE = "active"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    RELEASED = "released"


class OutboxStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    RETRY = "retry"
    FAILED = "failed"


class JobPhotoCategory(StrEnum):
    BEFORE = "before"
    AFTER = "after"
    DAMAGE = "damage"
    ISSUE = "issue"


class JobPhotoStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"


class ComplaintStatus(StrEnum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    REWASH_APPROVED = "rewash_approved"

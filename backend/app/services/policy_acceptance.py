import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import StaffContext
from app.domain.errors import ConflictError, DomainError
from app.models.entities import AuditEvent, Booking
from app.schemas.policies import PolicyAcceptance, StaffPolicyProvision
from app.services.customer_communications import queue_customer_email_if_available

POLICY_REVISION = "2026-11-10.2"
POLICY_VERSIONS = {
    slug: f"{slug}@{POLICY_REVISION}"
    for slug in ("terms-and-conditions", "cancellation-and-refund-policy", "privacy-policy")
}


def require_policy_acceptance(value: PolicyAcceptance | None) -> PolicyAcceptance:
    if value is None or not value.accepted:
        raise DomainError(
            "POLICY_ACCEPTANCE_REQUIRED",
            "Agree to the booking policies before confirming.",
            status_code=422,
        )
    require_current_revision(value.revision)
    return value


def require_current_revision(revision: str) -> None:
    if revision != POLICY_REVISION:
        raise ConflictError(
            "POLICY_VERSION_CHANGED",
            "The booking policies have changed. Reload the page and review them again.",
        )


def record_checkout_acceptance(
    session: AsyncSession,
    *,
    booking_id: uuid.UUID,
    business_id: uuid.UUID,
    auth_user_id: uuid.UUID | None,
    acceptance: PolicyAcceptance,
) -> None:
    session.add(
        AuditEvent(
            business_id=business_id,
            actor_auth_user_id=auth_user_id,
            event_type="booking_policies_accepted",
            entity_type="booking",
            entity_id=booking_id,
            metadata_json={
                "channel": "online_checkout",
                "customer_identity": "account" if auth_user_id else "guest_booking_contact",
                "language": acceptance.language,
                "policy_versions": POLICY_VERSIONS,
            },
        )
    )


async def record_staff_provision(
    session: AsyncSession,
    context: StaffContext,
    booking_id: uuid.UUID,
    provision: StaffPolicyProvision,
) -> bool:
    require_current_revision(provision.revision)
    booking = await session.scalar(
        select(Booking)
        .where(Booking.id == booking_id, Booking.business_id == context.business_id)
        .with_for_update()
    )
    if booking is None:
        raise DomainError("BOOKING_NOT_FOUND", "Booking not found.", status_code=404)
    if provision.channel == "email" and not booking.customer_email:
        raise DomainError("BOOKING_EMAIL_MISSING", "This booking has no email address.")

    event = AuditEvent(
        id=uuid.uuid4(),
        business_id=context.business_id,
        actor_auth_user_id=context.auth_user_id,
        event_type="booking_policies_provided_by_staff",
        entity_type="booking",
        entity_id=booking.id,
        metadata_json={
            "channel": provision.channel,
            "language": provision.language,
            "policy_versions": POLICY_VERSIONS,
            "delivery": "queued" if provision.channel == "email" else "staff_attested",
        },
    )
    session.add(event)
    if provision.channel != "email":
        return False
    queued = queue_customer_email_if_available(
        session,
        business_id=context.business_id,
        booking_id=booking.id,
        notification_type="booking_policies_provided",
        dedupe_key=f"booking-policies-provided:{event.id}",
        recipient=booking.customer_email,
        payload={"booking_reference": booking.reference, "language": provision.language},
        next_attempt_at=datetime.now(UTC),
    )
    return queued is not None

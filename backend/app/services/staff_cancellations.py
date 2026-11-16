import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import StaffContext
from app.domain.enums import BookingStatus, CancellationStatus, JobStatus, SlotStatus, StaffRole
from app.domain.errors import ConflictError, DomainError
from app.models.entities import (
    AuditEvent,
    Booking,
    CancellationRequest,
    Job,
    JobEvent,
    ScheduleSlot,
)
from app.schemas.staff import StaffBookingCancellation, StaffBookingCancellationResult
from app.services.customer_communications import (
    discard_unsent_appointment_reminders,
    queue_customer_email_if_available,
)
from app.services.loyalty import release_booking_rewards
from app.services.smart_scheduling import lock_schedule_day


async def cancel_staff_booking(
    session: AsyncSession,
    context: StaffContext,
    booking_id: uuid.UUID,
    request: StaffBookingCancellation,
) -> StaffBookingCancellationResult:
    if context.role not in {StaffRole.MANAGER, StaffRole.ADMIN}:
        raise DomainError("INSUFFICIENT_ROLE", "Manager access is required.", status_code=403)
    start = await session.scalar(
        select(Booking.scheduled_start).where(
            Booking.id == booking_id,
            Booking.business_id == context.business_id,
        )
    )
    if start is None:
        raise DomainError("BOOKING_NOT_FOUND", "Booking not found.", status_code=404)
    await lock_schedule_day(
        session,
        business_id=context.business_id,
        day=start.astimezone(ZoneInfo(context.timezone)).date(),
    )
    row = (
        await session.execute(
            select(Booking, Job)
            .join(Job, Job.booking_id == Booking.id)
            .where(
                Booking.id == booking_id,
                Booking.business_id == context.business_id,
                Job.business_id == context.business_id,
            )
            .with_for_update()
        )
    ).one_or_none()
    if row is None:
        raise DomainError("BOOKING_NOT_FOUND", "Booking not found.", status_code=404)
    booking, job = row
    if booking.scheduled_start != start or job.version != request.expected_version:
        raise ConflictError("STALE_JOB_VERSION", "This appointment changed. Refresh its details.")
    if booking.status not in {
        BookingStatus.CONFIRMED,
        BookingStatus.CANCELLATION_REQUESTED,
        BookingStatus.RESCHEDULING_REQUIRED,
    } or job.status not in {
        JobStatus.UNASSIGNED,
        JobStatus.ASSIGNED,
        JobStatus.EN_ROUTE,
        JobStatus.ARRIVED,
        JobStatus.RESCHEDULING_REQUIRED,
    }:
        raise ConflictError("BOOKING_NOT_CANCELLABLE", "This appointment cannot be cancelled.")

    now = datetime.now(UTC)
    await discard_unsent_appointment_reminders(session, booking.id)
    booking.status = BookingStatus.CANCELLED
    job.status = JobStatus.CANCELLED
    booking.version += 1
    job.version += 1
    # Release reserved capacity, preserving both booking and financial records.
    await session.execute(
        update(ScheduleSlot)
        .where(
            ScheduleSlot.booking_id == booking.id,
        )
        .values(
            status=SlotStatus.FREE,
            booking_id=None,
            hold_group_id=None,
            hold_expires_at=None,
            version=ScheduleSlot.version + 1,
        )
    )
    await release_booking_rewards(session, business_id=context.business_id, booking=booking)
    pending = list(
        (
            await session.scalars(
                select(CancellationRequest)
                .where(
                    CancellationRequest.booking_id == booking.id,
                    CancellationRequest.status == CancellationStatus.REQUESTED,
                )
                .with_for_update()
            )
        ).all()
    )
    if not pending:
        pending = [
            CancellationRequest(
                booking_id=booking.id,
                requester_type="staff",
                requested_at=now,
                reason=request.reason,
            )
        ]
        session.add_all(pending)
    for cancellation in pending:
        cancellation.status = CancellationStatus.APPROVED
        cancellation.reviewed_by_staff_id = context.staff_id
        cancellation.reviewed_at = now
        cancellation.review_note = request.reason
    try:
        recipient = str(TypeAdapter(EmailStr).validate_python(booking.customer_email))
    except ValidationError:
        recipient = None
    email = queue_customer_email_if_available(
        session,
        business_id=context.business_id,
        booking_id=booking.id,
        notification_type="booking_cancelled",
        dedupe_key=f"booking-cancelled:{booking.id}",
        recipient=recipient,
        payload={
            "booking_reference": booking.reference,
            "reason": request.reason,
            "language": request.language,
            "scheduled_start": booking.scheduled_start.isoformat(),
            "scheduled_end": booking.scheduled_end.isoformat(),
        },
        next_attempt_at=now,
    )
    detail = {
        "reason": request.reason,
        "review_note": request.reason,
        "email_queued": email is not None,
        "manual_notification_required": email is None,
    }
    session.add_all(
        [
            JobEvent(
                job_id=job.id,
                booking_id=booking.id,
                actor_staff_id=context.staff_id,
                event_type="booking_cancelled",
                metadata_json=detail,
            ),
            AuditEvent(
                business_id=context.business_id,
                actor_auth_user_id=context.auth_user_id,
                entity_type="booking",
                entity_id=booking.id,
                event_type="staff_booking_cancelled",
                metadata_json=detail,
            ),
        ]
    )
    if email is None:
        session.add(
            JobEvent(
                job_id=job.id,
                booking_id=booking.id,
                actor_staff_id=context.staff_id,
                event_type="customer_manual_notification_required",
                metadata_json=detail,
            )
        )
    await session.flush()
    return StaffBookingCancellationResult(
        booking_id=booking.id,
        job_id=job.id,
        email_queued=email is not None,
        manual_notification_required=email is None,
    )

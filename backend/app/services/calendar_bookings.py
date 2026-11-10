import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import StaffContext
from app.domain.enums import BookingStatus, JobStatus, PaymentStatus, SlotStatus, StaffRole
from app.domain.errors import ConflictError, DomainError
from app.models.entities import (
    AuditEvent,
    Booking,
    Job,
    JobEvent,
    Payment,
    PaymentTransaction,
    ScheduleSlot,
    TeamMembership,
)
from app.repositories.business import BusinessConfiguration
from app.schemas.calendar_bookings import StaffBookingCreate, StaffBookingReceipt
from app.schemas.public import HoldCreate
from app.services.bookings import create_booking
from app.services.customer_communications import (
    discard_unsent_appointment_reminders,
    queue_customer_email_if_available,
)
from app.services.policy_acceptance import POLICY_VERSIONS, require_current_revision
from app.services.scheduling import create_hold
from app.services.smart_scheduling import lock_schedule_day


async def calendar_booking_team_scope(
    session: AsyncSession, context: StaffContext, *, lock: bool = False
) -> set[uuid.UUID] | None:
    if context.role in {StaffRole.MANAGER, StaffRole.ADMIN}:
        return None
    statement = select(TeamMembership.resource_id).where(
        TeamMembership.staff_profile_id == context.staff_id,
        TeamMembership.is_active.is_(True),
    )
    if lock:
        statement = statement.with_for_update(read=True)
    return set((await session.scalars(statement)).all())


@dataclass(frozen=True)
class DisplacedAppointment:
    booking: Booking
    job: Job
    team_id: uuid.UUID
    staff_id: uuid.UUID | None


async def _displace_appointment(
    session: AsyncSession,
    context: StaffContext,
    configuration: BusinessConfiguration,
    request: StaffBookingCreate,
    team_scope: set[uuid.UUID] | None,
) -> DisplacedAppointment:
    replacement = request.replacement
    if replacement is None:
        raise RuntimeError("Replacement details are required.")
    target = select(Job.booking_id).where(
        Job.id == replacement.job_id, Job.business_id == context.business_id
    )
    if team_scope is not None:
        target = target.where(Job.assigned_resource_id.in_(team_scope))
    booking = await session.scalar(
        select(Booking)
        .where(Booking.id == target.scalar_subquery(), Booking.business_id == context.business_id)
        .with_for_update()
    )
    if booking is None:
        raise DomainError("APPOINTMENT_NOT_FOUND", "Appointment not found.", status_code=404)
    # Existing staff lifecycle actions lock the job before updating its booking.
    # Fail on an in-flight job mutation instead of waiting while holding the booking.
    job = await session.scalar(
        select(Job)
        .where(Job.id == replacement.job_id, Job.booking_id == booking.id)
        .with_for_update(skip_locked=True)
    )
    if job is None or job.version != replacement.expected_version:
        raise ConflictError(
            "JOB_VERSION_CONFLICT", "The appointment changed. Refresh the calendar."
        )
    team_id = job.assigned_resource_id
    if team_scope is not None and team_id not in team_scope:
        raise DomainError("APPOINTMENT_NOT_FOUND", "Appointment not found.", status_code=404)
    if (
        job.status != JobStatus.ASSIGNED
        or booking.status != BookingStatus.CONFIRMED
        or booking.archived_at is not None
        or job.en_route_at is not None
        or job.started_at is not None
        or job.completed_at is not None
        or team_id is None
        or team_id != booking.resource_id
    ):
        raise ConflictError(
            "APPOINTMENT_NOT_REPLACEABLE", "Only an assigned future appointment can be replaced."
        )
    start = datetime.combine(
        request.date, request.time, ZoneInfo(configuration.settings.timezone)
    ).astimezone(UTC)
    if start != booking.scheduled_start or start != job.scheduled_start:
        raise ConflictError("REPLACEMENT_TIME_CHANGED", "Refresh the occupied appointment.")
    await lock_schedule_day(session, business_id=context.business_id, day=request.date)
    if start <= datetime.now(UTC):
        raise ConflictError(
            "APPOINTMENT_NOT_REPLACEABLE", "Only future appointments can be replaced."
        )
    slots = (
        await session.scalars(
            select(ScheduleSlot)
            .where(ScheduleSlot.booking_id == booking.id)
            .order_by(ScheduleSlot.slot_start, ScheduleSlot.id)
            .with_for_update()
        )
    ).all()
    if (
        not slots
        or slots[0].slot_start != start
        or any(slot.status != SlotStatus.RESERVED or slot.resource_id != team_id for slot in slots)
    ):
        raise ConflictError(
            "BOOKING_SLOT_CONFLICT", "The occupied capacity could not be released safely."
        )

    has_payment_dependency = await session.scalar(
        select(
            select(Payment.id)
            .where(
                Payment.booking_id == booking.id,
                or_(
                    Payment.provider_payment_id.is_not(None),
                    (Payment.amount_minor > 0)
                    & Payment.status.in_(
                        [PaymentStatus.PAID, PaymentStatus.PENDING, PaymentStatus.REFUND_PENDING]
                    ),
                    select(PaymentTransaction.id)
                    .where(
                        PaymentTransaction.payment_id == Payment.id,
                        PaymentTransaction.amount_minor > 0,
                    )
                    .exists(),
                ),
            )
            .exists()
        )
    )
    displaced = DisplacedAppointment(booking, job, team_id, job.assigned_staff_id)
    for slot in slots:
        slot.status = SlotStatus.FREE
        slot.booking_id = slot.hold_group_id = slot.hold_expires_at = None
        slot.version += 1
    booking.status = BookingStatus.RESCHEDULING_REQUIRED
    booking.reschedule_payment_review_required |= bool(has_payment_dependency)
    booking.version += 1
    job.status = JobStatus.RESCHEDULING_REQUIRED
    job.assigned_staff_id = job.assigned_resource_id = None
    job.assignment_source = job.assigned_at = job.assigned_by_staff_id = None
    job.version += 1
    await discard_unsent_appointment_reminders(session, booking.id)
    await session.flush()
    return displaced


async def book_from_calendar(
    session: AsyncSession,
    context: StaffContext,
    configuration: BusinessConfiguration,
    request: StaffBookingCreate,
) -> StaffBookingReceipt:
    require_current_revision(request.policy_revision)
    team_scope = await calendar_booking_team_scope(session, context, lock=True)
    if team_scope == set():
        raise DomainError(
            "STAFF_TEAM_REQUIRED",
            "An active team assignment is required to book from this calendar.",
            status_code=403,
        )
    displaced = None
    if request.replacement:
        displaced = await _displace_appointment(
            session, context, configuration, request, team_scope
        )
        team_scope = {displaced.team_id}

    hold = await create_hold(
        session,
        HoldCreate(
            date=request.date,
            start_time=request.time,
            vehicle_count=len(request.vehicles),
            service_ids=[item.service_id for item in request.vehicles],
            addon_ids=[addon for item in request.vehicles for addon in item.addon_ids],
        ),
        configuration=configuration,
        allowed_team_ids=team_scope,
        replacement_start=displaced.booking.scheduled_start if displaced else None,
    )
    # Request sessions disable autoflush. Confirmation reads the held slot rows
    # before it can consume them within this same transaction.
    await session.flush()
    created = await create_booking(
        session,
        request,
        None,
        staff_context=context,
        staff_hold_token=hold.hold_token,
        configuration=configuration,
    )
    job = (await session.scalars(select(Job).where(Job.booking_id == created.id))).one()
    session.add_all(
        [
            AuditEvent(
                business_id=context.business_id,
                actor_auth_user_id=context.auth_user_id,
                event_type="staff_calendar_booking_created",
                entity_type="booking",
                entity_id=created.id,
                metadata_json={"channel": "staff_calendar", "job_id": str(job.id)},
            ),
            AuditEvent(
                business_id=context.business_id,
                actor_auth_user_id=context.auth_user_id,
                event_type="booking_policies_provided_by_staff",
                entity_type="booking",
                entity_id=created.id,
                metadata_json={
                    "channel": "staff_calendar",
                    "language": request.language,
                    "policy_versions": POLICY_VERSIONS,
                    "delivery": "queued"
                    if request.policy_delivery == "email"
                    else "staff_attested",
                },
            ),
        ]
    )
    if displaced and request.replacement:
        previous = displaced.booking
        queued = queue_customer_email_if_available(
            session,
            business_id=context.business_id,
            booking_id=previous.id,
            notification_type="booking_displaced",
            dedupe_key=f"booking-displaced:{previous.id}:{previous.version}",
            recipient=previous.customer_email,
            payload={
                "booking_reference": previous.reference,
                "booking_version": previous.version,
                "scheduled_start": previous.scheduled_start.isoformat(),
            },
            next_attempt_at=datetime.now(UTC),
        )
        metadata = {
            "previous_booking_id": str(previous.id),
            "replacement_booking_id": str(created.id),
            "previous_start": previous.scheduled_start.isoformat(),
            "previous_end": previous.scheduled_end.isoformat(),
            "replacement_start": created.scheduled_start.isoformat(),
            "replacement_end": created.scheduled_end.isoformat(),
            "previous_team_id": str(displaced.team_id),
            "previous_staff_id": str(displaced.staff_id) if displaced.staff_id else None,
            "previous_status": BookingStatus.CONFIRMED,
            "status": BookingStatus.RESCHEDULING_REQUIRED,
            "reason": request.replacement.reason,
            "payment_review_required": previous.reschedule_payment_review_required,
            "customer_email_queued": queued is not None,
        }
        session.add_all(
            [
                AuditEvent(
                    business_id=context.business_id,
                    actor_auth_user_id=context.auth_user_id,
                    event_type="appointment_replaced",
                    entity_type="booking",
                    entity_id=previous.id,
                    metadata_json=metadata,
                ),
                JobEvent(
                    job_id=displaced.job.id,
                    booking_id=previous.id,
                    actor_staff_id=context.staff_id,
                    event_type="appointment_displaced",
                    metadata_json=metadata,
                ),
                JobEvent(
                    job_id=job.id,
                    booking_id=created.id,
                    actor_staff_id=context.staff_id,
                    event_type="replacement_appointment_created",
                    metadata_json={},
                ),
            ]
        )
    return StaffBookingReceipt(
        id=created.id,
        job_id=job.id,
        reference=created.reference,
        scheduled_start=created.scheduled_start,
        scheduled_end=created.scheduled_end,
        total_amount_minor=created.total_amount_minor,
        replaced_appointment=displaced is not None,
    )

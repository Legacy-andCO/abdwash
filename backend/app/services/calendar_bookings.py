import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import StaffContext
from app.domain.enums import StaffRole
from app.domain.errors import ConflictError, DomainError
from app.models.entities import (
    AuditEvent,
    Booking,
    Job,
    TeamMembership,
)
from app.repositories.business import BusinessConfiguration
from app.schemas.calendar_bookings import StaffBookingCreate, StaffBookingReceipt
from app.schemas.public import HoldCreate
from app.services.bookings import create_booking
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
    overlap_team = request.overlap.team_id if request.overlap else None
    if overlap_team is not None and team_scope is not None and overlap_team not in team_scope:
        raise DomainError("TEAM_NOT_FOUND", "Team not found.", status_code=404)

    if request.overlap:
        # An exception must identify the occupied appointment the user selected.
        # Serialize with normal booking/reschedule/cancellation before checking it.
        await lock_schedule_day(session, business_id=context.business_id, day=request.date)
        source = await session.scalar(
            select(Job)
            .join(Booking, Booking.id == Job.booking_id)
            .where(
                Job.id == request.overlap.job_id,
                Job.business_id == context.business_id,
                Booking.business_id == context.business_id,
                Job.assigned_resource_id == overlap_team,
                Job.status.in_(["assigned", "en_route", "arrived", "in_progress"]),
                Booking.status == "confirmed",
            )
            .with_for_update()
        )
        if source is None:
            raise DomainError(
                "APPOINTMENT_NOT_FOUND", "The selected appointment is unavailable.", status_code=404
            )
        if source.version != request.overlap.expected_version:
            raise ConflictError(
                "STALE_JOB_VERSION", "This appointment changed. Refresh the calendar."
            )

        requested_start = datetime.combine(request.date, request.time, ZoneInfo(context.timezone))
        if not source.scheduled_start <= requested_start < source.scheduled_end:
            raise ConflictError(
                "NO_APPOINTMENT_OVERLAP", "Choose a time inside the selected appointment."
            )

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
        overlap_team_id=overlap_team,
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
    if overlap_team is not None:
        assert request.overlap is not None
        session.add(
            AuditEvent(
                business_id=context.business_id,
                actor_auth_user_id=context.auth_user_id,
                event_type="staff_calendar_capacity_exception",
                entity_type="booking",
                entity_id=created.id,
                metadata_json={
                    "actor_staff_id": str(context.staff_id),
                    "team_id": str(overlap_team),
                    "selected_job_id": str(request.overlap.job_id),
                    "scheduled_start": created.scheduled_start.isoformat(),
                    "scheduled_end": created.scheduled_end.isoformat(),
                    "job_id": str(job.id),
                    "capacity_exception": True,
                },
            )
        )
    return StaffBookingReceipt(
        id=created.id,
        job_id=job.id,
        reference=created.reference,
        scheduled_start=created.scheduled_start.astimezone(UTC),
        scheduled_end=created.scheduled_end.astimezone(UTC),
        total_amount_minor=created.total_amount_minor,
        capacity_exception=overlap_team is not None,
    )

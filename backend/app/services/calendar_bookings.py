import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import StaffContext
from app.domain.enums import StaffRole
from app.domain.errors import DomainError
from app.models.entities import (
    AuditEvent,
    Job,
    TeamMembership,
)
from app.repositories.business import BusinessConfiguration
from app.schemas.calendar_bookings import StaffBookingCreate, StaffBookingReceipt
from app.schemas.public import HoldCreate
from app.services.bookings import create_booking
from app.services.policy_acceptance import POLICY_VERSIONS, require_current_revision
from app.services.scheduling import create_hold


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
        scheduled_start=created.scheduled_start,
        scheduled_end=created.scheduled_end,
        total_amount_minor=created.total_amount_minor,
        capacity_exception=overlap_team is not None,
    )

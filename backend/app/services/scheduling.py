import hashlib
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import HoldStatus, SlotStatus
from app.domain.errors import ConflictError, DomainError
from app.domain.scheduling import (
    SchedulePolicy,
    SlotWindow,
    generate_slot_windows,
    required_slot_count,
    resolve_requested_windows,
)
from app.domain.service_scheduling import (
    enforce_customer_start_time,
    required_customer_start_time,
)
from app.models.entities import (
    BusinessOperatingHour,
    BusinessSettings,
    ScheduleSlot,
    Service,
    SlotHoldGroup,
)
from app.repositories.business import BusinessConfiguration, load_default_business
from app.schemas.public import (
    AvailabilityResponse,
    AvailabilitySlot,
    HoldCreate,
    HoldResponse,
)
from app.services.smart_scheduling import (
    current_selection_duration_minutes,
    evaluate_team,
    evaluate_teams_for_interval,
    get_eligible_teams,
    load_capacity_items,
    lock_schedule_day,
    rank_evaluations,
)


def hold_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def policy_from_settings(settings: BusinessSettings) -> SchedulePolicy:
    return SchedulePolicy(
        timezone=settings.timezone,
        opening_time=settings.opening_time,
        closing_time=settings.closing_time,
        slot_duration_minutes=settings.slot_duration_minutes,
        multi_vehicle_threshold=settings.multi_vehicle_threshold,
        multi_vehicle_required_slots=settings.multi_vehicle_required_slots,
        hold_duration_minutes=settings.hold_duration_minutes,
    )


async def policy_for_day(
    session: AsyncSession, settings: BusinessSettings, day: date
) -> SchedulePolicy | None:
    hours = await session.scalar(
        select(BusinessOperatingHour).where(
            BusinessOperatingHour.business_id == settings.business_id,
            BusinessOperatingHour.weekday == day.weekday(),
        )
    )
    if hours is None:
        return policy_from_settings(settings)
    if not hours.is_open or hours.opening_time is None or hours.closing_time is None:
        return None
    return SchedulePolicy(
        timezone=settings.timezone,
        opening_time=hours.opening_time,
        closing_time=hours.closing_time,
        slot_duration_minutes=settings.slot_duration_minutes,
        multi_vehicle_threshold=settings.multi_vehicle_threshold,
        multi_vehicle_required_slots=settings.multi_vehicle_required_slots,
        hold_duration_minutes=settings.hold_duration_minutes,
    )


async def availability_for_date(
    session: AsyncSession,
    *,
    day: date,
    vehicle_count: int,
    service_ids: list[uuid.UUID] | None = None,
    addon_ids: list[uuid.UUID] | None = None,
    configuration: BusinessConfiguration | None = None,
    allowed_team_ids: set[uuid.UUID] | None = None,
) -> AvailabilityResponse:
    staff_booking = configuration is not None
    configuration = configuration or await load_default_business(session)
    policy = await policy_for_day(session, configuration.settings, day)
    if policy is None:
        return AvailabilityResponse(
            date=day,
            timezone=configuration.settings.timezone,
            vehicle_count=vehicle_count,
            required_slot_count=required_slot_count(
                vehicle_count,
                configuration.settings.multi_vehicle_threshold,
                configuration.settings.multi_vehicle_required_slots,
            ),
            slots=[],
        )
    selected_service_names = await _selected_service_names(
        session,
        business_id=configuration.business.id,
        service_ids=service_ids or [],
    )
    required_start = required_customer_start_time(selected_service_names)
    windows = generate_slot_windows(day, policy)
    required = required_slot_count(
        vehicle_count, policy.multi_vehicle_threshold, policy.multi_vehicle_required_slots
    )
    floor_minutes = required * policy.slot_duration_minutes
    expected_minutes = await current_selection_duration_minutes(
        session,
        business_id=configuration.business.id,
        service_ids=service_ids or [],
        addon_ids=addon_ids or [],
        vehicle_count=vehicle_count,
        reserved_slot_floor_minutes=floor_minutes,
    )
    teams = await get_eligible_teams(session, business_id=configuration.business.id, day=day)
    if allowed_team_ids is not None:
        teams = [team for team in teams if team.id in allowed_team_ids]
    if not windows:
        return AvailabilityResponse(
            date=day,
            timezone=policy.timezone,
            vehicle_count=vehicle_count,
            required_slot_count=required,
            required_start_time=required_start,
            slots=[],
        )
    starts = [window.start for window in windows]
    existing = list(
        (
            await session.scalars(
                select(ScheduleSlot).where(
                    ScheduleSlot.resource_id.in_([team.id for team in teams]),
                    ScheduleSlot.slot_start.in_(starts),
                )
            )
        ).all()
    )
    now = datetime.now(UTC)
    occupancy = {(slot.resource_id, slot.slot_start): _slot_blocks(slot, now) for slot in existing}
    capacity_items = await load_capacity_items(
        session,
        business_id=configuration.business.id,
        resource_ids=[team.id for team in teams],
        day=day,
        timezone=policy.timezone,
        include_blocked_slots=staff_booking,
    )
    output: list[AvailabilitySlot] = []
    zone = ZoneInfo(policy.timezone)
    for index, window in enumerate(windows):
        if (
            required_start is not None
            and window.start.astimezone(zone).time().replace(tzinfo=None) != required_start
        ):
            continue
        sequence_fits = index + required <= len(windows)
        operational_end = window.start + timedelta(minutes=expected_minutes)
        available = False
        if sequence_fits and window.start > now:
            needed = windows[index : index + required]
            for team in teams:
                if all(not occupancy.get((team.id, item.start), False) for item in needed):
                    evaluation = evaluate_team(
                        team,
                        capacity_items,
                        starts_at=window.start,
                        ends_at=operational_end,
                        turnaround_minutes=configuration.settings.default_team_turnaround_minutes,
                    )
                    if evaluation.feasible:
                        available = True
                        break
        reason = None
        if window.start <= now:
            reason = "PAST_SLOT"
        elif not sequence_fits:
            reason = "CONSECUTIVE_SLOT_OUTSIDE_HOURS"
        elif not available:
            reason = "NO_TEAM_CAPACITY"
        output.append(
            AvailabilitySlot(
                time=window.start.astimezone(zone).time().replace(tzinfo=None),
                starts_at=window.start,
                ends_at=operational_end,
                available=available,
                required_slot_count=required,
                unavailable_reason=reason,
            )
        )
    return AvailabilityResponse(
        date=day,
        timezone=policy.timezone,
        vehicle_count=vehicle_count,
        required_slot_count=required,
        required_start_time=required_start,
        slots=output,
    )


def _slot_blocks(slot: ScheduleSlot, now: datetime) -> bool:
    if slot.status == SlotStatus.HELD:
        return slot.hold_expires_at is not None and slot.hold_expires_at > now
    return slot.status in {SlotStatus.RESERVED, SlotStatus.BLOCKED}


async def create_hold(
    session: AsyncSession,
    request: HoldCreate,
    *,
    configuration: BusinessConfiguration | None = None,
    allowed_team_ids: set[uuid.UUID] | None = None,
    replacement_start: datetime | None = None,
) -> HoldResponse:
    staff_booking = configuration is not None
    configuration = configuration or await load_default_business(session)
    policy = await policy_for_day(session, configuration.settings, request.date)
    if policy is None:
        raise DomainError("BUSINESS_CLOSED", "The business is closed on this day.")
    selected_service_names = await _selected_service_names(
        session,
        business_id=configuration.business.id,
        service_ids=request.service_ids,
    )
    enforce_customer_start_time(selected_service_names, request.start_time)
    if replacement_start is None:
        windows = resolve_requested_windows(
            request.date, request.start_time, request.vehicle_count, policy
        )
    else:
        zone = ZoneInfo(policy.timezone)
        local_start = replacement_start.astimezone(zone)
        if (
            replacement_start <= datetime.now(UTC)
            or local_start.date() != request.date
            or local_start.time() != request.start_time
        ):
            raise ConflictError("REPLACEMENT_TIME_CHANGED", "Refresh the occupied appointment.")
        count = required_slot_count(
            request.vehicle_count,
            policy.multi_vehicle_threshold,
            policy.multi_vehicle_required_slots,
        )
        duration = timedelta(minutes=policy.slot_duration_minutes)
        windows = [
            SlotWindow(replacement_start + i * duration, replacement_start + (i + 1) * duration)
            for i in range(count)
        ]
        if local_start.time() < policy.opening_time or windows[-1].start > datetime.combine(
            request.date, policy.closing_time, zone
        ):
            raise ConflictError(
                "OUTSIDE_OPERATING_HOURS", "The requested slots do not fit business hours."
            )
    required = len(windows)
    floor_minutes = required * policy.slot_duration_minutes
    expected_minutes = await current_selection_duration_minutes(
        session,
        business_id=configuration.business.id,
        service_ids=request.service_ids,
        addon_ids=request.addon_ids,
        vehicle_count=request.vehicle_count,
        reserved_slot_floor_minutes=floor_minutes,
    )
    operational_end = windows[0].start + timedelta(minutes=expected_minutes)
    if staff_booking and operational_end > datetime.combine(
        request.date + timedelta(days=1), datetime.min.time(), ZoneInfo(policy.timezone)
    ):
        raise ConflictError(
            "OUTSIDE_OPERATING_HOURS", "The appointment must finish on the same day."
        )
    await lock_schedule_day(session, business_id=configuration.business.id, day=request.date)
    if staff_booking and windows[0].start <= datetime.now(UTC):
        raise ConflictError("PAST_SLOT", "Appointments cannot be booked in the past.")
    # A candidate can pass operational capacity while a manually blocked grid
    # slot still prevents this exact start. Try ranked candidates in order by
    # excluding each blocked candidate from the local attempt.
    evaluations = await evaluate_teams_for_interval(
        session,
        business_id=configuration.business.id,
        day=request.date,
        timezone=policy.timezone,
        starts_at=windows[0].start,
        ends_at=operational_end,
        turnaround_minutes=configuration.settings.default_team_turnaround_minutes,
        include_blocked_slots=staff_booking,
    )
    ranked = rank_evaluations(evaluations)
    if allowed_team_ids is not None:
        ranked = [item for item in ranked if item.team.id in allowed_team_ids]
    now = datetime.now(UTC)
    grid_rows = (
        list(
            (
                await session.scalars(
                    select(ScheduleSlot).where(
                        ScheduleSlot.resource_id.in_([item.team.id for item in ranked]),
                        ScheduleSlot.slot_start.in_([window.start for window in windows]),
                    )
                )
            ).all()
        )
        if ranked
        else []
    )
    blocked_grid = {
        (slot.resource_id, slot.slot_start) for slot in grid_rows if _slot_blocks(slot, now)
    }
    candidates = [
        item
        for item in ranked
        if all((item.team.id, window.start) not in blocked_grid for window in windows)
    ]
    for evaluation in candidates:
        resource = evaluation.team
        slots = await _lock_slot_sequence(
            session,
            business_id=configuration.business.id,
            resource_id=resource.id,
            windows=windows,
        )
        if slots is None:
            continue
        raw_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(minutes=policy.hold_duration_minutes)
        group = SlotHoldGroup(
            business_id=configuration.business.id,
            resource_id=resource.id,
            token_hash=hold_token_hash(raw_token),
            status=HoldStatus.ACTIVE,
            vehicle_count=request.vehicle_count,
            required_slot_count=len(windows),
            expected_duration_minutes=expected_minutes,
            slot_start=windows[0].start,
            slot_end=operational_end,
            expires_at=expires_at,
        )
        session.add(group)
        await session.flush()
        for slot in slots:
            slot.status = SlotStatus.HELD
            slot.hold_group_id = group.id
            slot.hold_expires_at = expires_at
            slot.booking_id = None
            slot.version += 1
        return HoldResponse(
            hold_token=raw_token,
            starts_at=windows[0].start,
            ends_at=operational_end,
            expires_at=expires_at,
            required_slot_count=len(windows),
        )

    raise ConflictError(
        "NO_TEAM_CAPACITY",
        "This time is no longer available. Please choose another time.",
    )


async def lock_hold_for_confirmation(
    session: AsyncSession,
    token: str,
    *,
    business_id: uuid.UUID,
    timezone: str,
    previous_day: date | None = None,
) -> SlotHoldGroup | None:
    conditions = (
        SlotHoldGroup.token_hash == hold_token_hash(token),
        SlotHoldGroup.business_id == business_id,
    )
    start = await session.scalar(select(SlotHoldGroup.slot_start).where(*conditions))
    if start is None:
        return None
    day = start.astimezone(ZoneInfo(timezone)).date()
    days = {day} if previous_day is None else {day, previous_day}
    for locked_day in sorted(days):
        await lock_schedule_day(session, business_id=business_id, day=locked_day)
    return (
        await session.scalars(
            select(SlotHoldGroup)
            .where(*conditions)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).one_or_none()


async def _selected_service_names(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    service_ids: list[uuid.UUID],
) -> list[str]:
    if not service_ids:
        return []
    return list(
        (
            await session.scalars(
                select(Service.name).where(
                    Service.business_id == business_id,
                    Service.id.in_(set(service_ids)),
                    Service.is_active.is_(True),
                    Service.mobile_available.is_(True),
                )
            )
        ).all()
    )


async def _lock_slot_sequence(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    resource_id: uuid.UUID,
    windows: list[SlotWindow],
) -> list[ScheduleSlot] | None:
    ordered = sorted(windows, key=lambda item: item.start)
    for window in ordered:
        lock_key = f"schedule:{resource_id}:{window.start.isoformat()}"
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": lock_key}
        )
        await session.execute(
            insert(ScheduleSlot)
            .values(
                business_id=business_id,
                resource_id=resource_id,
                slot_start=window.start,
                slot_end=window.end,
                status=SlotStatus.FREE,
            )
            .on_conflict_do_nothing(index_elements=["resource_id", "slot_start"])
        )
    starts = [window.start for window in ordered]
    slots = list(
        (
            await session.scalars(
                select(ScheduleSlot)
                .where(
                    ScheduleSlot.resource_id == resource_id,
                    ScheduleSlot.slot_start.in_(starts),
                )
                .order_by(ScheduleSlot.slot_start)
                .with_for_update()
            )
        ).all()
    )
    now = datetime.now(UTC)
    expired_group_ids: set[uuid.UUID] = set()
    for slot in slots:
        if (
            slot.status == SlotStatus.HELD
            and slot.hold_expires_at is not None
            and slot.hold_expires_at <= now
        ):
            if slot.hold_group_id:
                expired_group_ids.add(slot.hold_group_id)
            slot.status = SlotStatus.FREE
            slot.hold_group_id = None
            slot.hold_expires_at = None
            slot.booking_id = None
            slot.version += 1
    if expired_group_ids:
        await session.execute(
            update(SlotHoldGroup)
            .where(
                SlotHoldGroup.id.in_(expired_group_ids), SlotHoldGroup.status == HoldStatus.ACTIVE
            )
            .values(status=HoldStatus.EXPIRED)
        )
    if len(slots) != len(ordered) or any(_slot_blocks(slot, now) for slot in slots):
        return None
    return slots

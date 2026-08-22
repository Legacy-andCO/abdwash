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
from app.models.entities import (
    BusinessSettings,
    ScheduleResource,
    ScheduleSlot,
    SlotHoldGroup,
)
from app.repositories.business import load_default_business
from app.schemas.public import (
    AvailabilityResource,
    AvailabilityResponse,
    AvailabilitySlot,
    HoldCreate,
    HoldResponse,
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


async def availability_for_date(
    session: AsyncSession, *, day: date, vehicle_count: int
) -> AvailabilityResponse:
    configuration = await load_default_business(session)
    policy = policy_from_settings(configuration.settings)
    windows = generate_slot_windows(day, policy)
    required = required_slot_count(
        vehicle_count, policy.multi_vehicle_threshold, policy.multi_vehicle_required_slots
    )
    resources = list(
        (
            await session.scalars(
                select(ScheduleResource)
                .where(
                    ScheduleResource.business_id == configuration.business.id,
                    ScheduleResource.is_active.is_(True),
                )
                .order_by(ScheduleResource.sort_order, ScheduleResource.name)
            )
        ).all()
    )
    if not windows:
        return AvailabilityResponse(
            date=day,
            timezone=policy.timezone,
            vehicle_count=vehicle_count,
            required_slot_count=required,
            slots=[],
        )
    starts = [window.start for window in windows]
    existing = list(
        (
            await session.scalars(
                select(ScheduleSlot).where(
                    ScheduleSlot.resource_id.in_([resource.id for resource in resources]),
                    ScheduleSlot.slot_start.in_(starts),
                )
            )
        ).all()
    )
    now = datetime.now(UTC)
    occupancy = {(slot.resource_id, slot.slot_start): _slot_blocks(slot, now) for slot in existing}
    output: list[AvailabilitySlot] = []
    zone = ZoneInfo(policy.timezone)
    for index, window in enumerate(windows):
        available_resources: list[AvailabilityResource] = []
        sequence_fits = index + required <= len(windows)
        if sequence_fits and window.start > now:
            needed = windows[index : index + required]
            for resource in resources:
                if all(not occupancy.get((resource.id, item.start), False) for item in needed):
                    available_resources.append(
                        AvailabilityResource(resource_id=resource.id, resource_name=resource.name)
                    )
        reason = None
        if window.start <= now:
            reason = "PAST_SLOT"
        elif not sequence_fits:
            reason = "CONSECUTIVE_SLOT_OUTSIDE_HOURS"
        elif not available_resources:
            reason = "CONSECUTIVE_SLOT_UNAVAILABLE" if required > 1 else "SLOT_UNAVAILABLE"
        output.append(
            AvailabilitySlot(
                time=window.start.astimezone(zone).time().replace(tzinfo=None),
                starts_at=window.start,
                ends_at=windows[index + required - 1].end if sequence_fits else window.end,
                available=bool(available_resources),
                required_slot_count=required,
                resources=available_resources,
                unavailable_reason=reason,
            )
        )
    return AvailabilityResponse(
        date=day,
        timezone=policy.timezone,
        vehicle_count=vehicle_count,
        required_slot_count=required,
        slots=output,
    )


def _slot_blocks(slot: ScheduleSlot, now: datetime) -> bool:
    if slot.status == SlotStatus.HELD:
        return slot.hold_expires_at is not None and slot.hold_expires_at > now
    return slot.status in {SlotStatus.RESERVED, SlotStatus.BLOCKED}


async def create_hold(session: AsyncSession, request: HoldCreate) -> HoldResponse:
    configuration = await load_default_business(session)
    policy = policy_from_settings(configuration.settings)
    windows = resolve_requested_windows(
        request.date, request.start_time, request.vehicle_count, policy
    )
    resource_statement = select(ScheduleResource).where(
        ScheduleResource.business_id == configuration.business.id,
        ScheduleResource.is_active.is_(True),
    )
    if request.resource_id:
        resource_statement = resource_statement.where(ScheduleResource.id == request.resource_id)
    resources = list(
        (await session.scalars(resource_statement.order_by(ScheduleResource.sort_order))).all()
    )
    if not resources:
        raise DomainError(
            "RESOURCE_NOT_FOUND", "No active scheduling resource was found.", status_code=404
        )

    for resource in resources:
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
            slot_start=windows[0].start,
            slot_end=windows[-1].end,
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
            resource_id=resource.id,
            starts_at=windows[0].start,
            ends_at=windows[-1].end,
            expires_at=expires_at,
            required_slot_count=len(windows),
        )

    code = "CONSECUTIVE_SLOT_UNAVAILABLE" if len(windows) > 1 else "SLOT_UNAVAILABLE"
    message = (
        "This booking requires consecutive slots and the following slot is unavailable."
        if len(windows) > 1
        else "The requested slot is unavailable."
    )
    raise ConflictError(code, message)


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

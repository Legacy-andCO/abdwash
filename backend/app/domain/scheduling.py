from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.domain.errors import DomainError


@dataclass(frozen=True)
class SchedulePolicy:
    timezone: str
    opening_time: time
    closing_time: time
    slot_duration_minutes: int
    multi_vehicle_threshold: int
    multi_vehicle_required_slots: int
    hold_duration_minutes: int


@dataclass(frozen=True)
class SlotWindow:
    start: datetime
    end: datetime


def required_slot_count(vehicle_count: int, threshold: int = 3, slots_at_threshold: int = 2) -> int:
    if vehicle_count < 1:
        raise DomainError("INVALID_VEHICLE_COUNT", "At least one vehicle is required.")
    return slots_at_threshold if vehicle_count >= threshold else 1


def generate_slot_windows(day: date, policy: SchedulePolicy) -> list[SlotWindow]:
    zone = ZoneInfo(policy.timezone)
    cursor = datetime.combine(day, policy.opening_time, tzinfo=zone)
    closing = datetime.combine(day, policy.closing_time, tzinfo=zone)
    duration = timedelta(minutes=policy.slot_duration_minutes)
    windows: list[SlotWindow] = []
    # Business closing time is the latest customer-selectable start. The
    # service's trusted duration continues to determine its operational end.
    while cursor <= closing:
        windows.append(SlotWindow(cursor.astimezone(UTC), (cursor + duration).astimezone(UTC)))
        cursor += duration
    return windows


def resolve_requested_windows(
    day: date,
    start_time: time,
    vehicle_count: int,
    policy: SchedulePolicy,
    *,
    now: datetime | None = None,
) -> list[SlotWindow]:
    slot_count = required_slot_count(
        vehicle_count, policy.multi_vehicle_threshold, policy.multi_vehicle_required_slots
    )
    all_windows = generate_slot_windows(day, policy)
    matching_index = next(
        (
            index
            for index, window in enumerate(all_windows)
            if window.start.astimezone(ZoneInfo(policy.timezone)).time().replace(tzinfo=None)
            == start_time.replace(tzinfo=None)
        ),
        None,
    )
    if matching_index is None or matching_index + slot_count > len(all_windows):
        raise DomainError("INVALID_SLOT", "The requested start time is outside business hours.")
    selected = all_windows[matching_index : matching_index + slot_count]
    current = now or datetime.now(UTC)
    if selected[0].start <= current:
        raise DomainError("PAST_SLOT", "Appointments cannot be booked in the past.")
    return selected


def cancellation_allowed(
    scheduled_start: datetime, cutoff_hours: int, *, now: datetime | None = None
) -> bool:
    current = now or datetime.now(UTC)
    return current <= scheduled_start - timedelta(hours=cutoff_hours)

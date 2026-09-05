from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.errors import DomainError
from app.domain.scheduling import (
    SchedulePolicy,
    cancellation_allowed,
    generate_slot_windows,
    required_slot_count,
    resolve_requested_windows,
)


@pytest.fixture
def policy() -> SchedulePolicy:
    return SchedulePolicy(
        timezone="Asia/Dubai",
        opening_time=time(9),
        closing_time=time(21),
        slot_duration_minutes=120,
        multi_vehicle_threshold=3,
        multi_vehicle_required_slots=2,
        hold_duration_minutes=10,
    )


@pytest.mark.parametrize(("vehicles", "expected"), [(1, 1), (2, 1), (3, 2), (4, 2), (20, 2)])
def test_required_slot_rule(vehicles: int, expected: int) -> None:
    assert required_slot_count(vehicles) == expected


def test_required_slots_rejects_empty_booking() -> None:
    with pytest.raises(DomainError, match="At least one"):
        required_slot_count(0)


def test_default_start_times_and_closing_boundary(policy: SchedulePolicy) -> None:
    windows = generate_slot_windows(date(2030, 1, 2), policy)
    local_times = [window.start.hour for window in windows]
    # Asia/Dubai is UTC+4 in January: 09,11,13,15,17,19,21 local.
    assert local_times == [5, 7, 9, 11, 13, 15, 17]
    assert windows[-1].end.hour == 19  # 23:00 local
    assert len(windows) == 7


def test_2100_is_the_latest_start(policy: SchedulePolicy) -> None:
    windows = resolve_requested_windows(
        date(2030, 1, 2), time(21), 1, policy, now=datetime(2029, 1, 1, tzinfo=UTC)
    )
    assert windows[0].start.astimezone(ZoneInfo(policy.timezone)).time() == time(21)


def test_after_2100_is_not_a_start(policy: SchedulePolicy) -> None:
    with pytest.raises(DomainError, match="outside business hours"):
        resolve_requested_windows(
            date(2030, 1, 2), time(23), 1, policy, now=datetime(2029, 1, 1, tzinfo=UTC)
        )


def test_three_vehicle_2100_cannot_fit_second_slot(policy: SchedulePolicy) -> None:
    with pytest.raises(DomainError, match="outside business hours"):
        resolve_requested_windows(
            date(2030, 1, 2), time(21), 3, policy, now=datetime(2029, 1, 1, tzinfo=UTC)
        )


def test_three_vehicle_booking_resolves_consecutive_windows(policy: SchedulePolicy) -> None:
    windows = resolve_requested_windows(
        date(2030, 1, 2), time(13), 3, policy, now=datetime(2029, 1, 1, tzinfo=UTC)
    )
    assert len(windows) == 2
    assert windows[0].end == windows[1].start
    assert windows[-1].end - windows[0].start == timedelta(hours=4)


def test_past_slot_rejected(policy: SchedulePolicy) -> None:
    with pytest.raises(DomainError, match="past"):
        resolve_requested_windows(
            date(2020, 1, 2), time(9), 1, policy, now=datetime(2029, 1, 1, tzinfo=UTC)
        )


def test_cancellation_cutoff() -> None:
    scheduled = datetime(2030, 1, 3, 12, tzinfo=UTC)
    assert cancellation_allowed(scheduled, 24, now=datetime(2030, 1, 2, 12, tzinfo=UTC))
    assert not cancellation_allowed(scheduled, 24, now=datetime(2030, 1, 2, 12, 0, 1, tzinfo=UTC))

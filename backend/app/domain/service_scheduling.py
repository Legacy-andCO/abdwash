from collections.abc import Iterable
from datetime import time

from app.domain.errors import DomainError

NINE_AM_START = time(9)
NINE_AM_ONLY_SERVICE_NAMES = frozenset(
    {
        "Interior Deep Cleaning",
        "Exterior Polishing",
    }
)


def required_customer_start_time(service_names: Iterable[str]) -> time | None:
    if NINE_AM_ONLY_SERVICE_NAMES.intersection(service_names):
        return NINE_AM_START
    return None


def enforce_customer_start_time(service_names: Iterable[str], start_time: time) -> None:
    required = required_customer_start_time(service_names)
    if required is not None and start_time.replace(tzinfo=None) != required:
        raise DomainError(
            "SERVICE_START_TIME_RESTRICTED",
            "This all-day service must start at 9:00 AM.",
            status_code=422,
        )

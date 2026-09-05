from datetime import time

import pytest

from app.domain.errors import DomainError
from app.domain.service_scheduling import (
    NINE_AM_START,
    enforce_customer_start_time,
    required_customer_start_time,
)


@pytest.mark.parametrize(
    "service_name",
    ["Interior Deep Cleaning", "Exterior Polishing"],
)
def test_big_services_require_nine_am(service_name: str) -> None:
    assert required_customer_start_time([service_name]) == NINE_AM_START
    enforce_customer_start_time([service_name], time(9))

    with pytest.raises(DomainError) as error:
        enforce_customer_start_time([service_name], time(14))

    assert error.value.code == "SERVICE_START_TIME_RESTRICTED"


def test_mixed_booking_inherits_nine_am_rule() -> None:
    names = ["Standard Wash", "Interior Deep Cleaning"]
    assert required_customer_start_time(names) == time(9)


def test_normal_service_has_no_special_start_restriction() -> None:
    assert required_customer_start_time(["Standard Wash"]) is None
    enforce_customer_start_time(["Standard Wash"], time(21))

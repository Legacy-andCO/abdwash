import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.api.staff as staff_api
from app.auth.dependencies import StaffContext, staff_context
from app.core.database import session_dependency
from app.domain.enums import StaffRole
from app.domain.errors import DomainError
from app.main import app
from app.models.entities import BookingService, BookingVehicle, Coupon, Service, ServicePrice
from app.schemas.coupons import (
    CouponCheckoutLine,
    CouponList,
    CouponValidationRequest,
    CouponWrite,
)
from app.services.booking_snapshots import vehicle_summaries_from_rows
from app.services.coupons import percentage_discount, resolve_coupon


class Rows:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


@pytest.mark.parametrize("code", ["AB", "ABCDEFG", "A B", "VIP-20", "VIP!"])
def test_coupon_schema_rejects_invalid_code(code: str) -> None:
    with pytest.raises(ValidationError):
        CouponValidationRequest(code=code, lines=[_line()])


@pytest.mark.parametrize(("code", "normalized"), [("ABC", "ABC"), ("a12b9c", "A12B9C")])
def test_coupon_schema_accepts_bounds_and_normalizes(code: str, normalized: str) -> None:
    assert CouponValidationRequest(code=code, lines=[_line()]).code == normalized


def test_coupon_manager_schema_requires_exact_percentage_and_unique_eligibility() -> None:
    service_id = uuid.uuid4()
    coupon = CouponWrite(
        code="VIP20",
        discount_percent=20,
        service_ids=[service_id],
        vehicle_types=["sedan"],
    )
    assert coupon.discount_percent == 20
    with pytest.raises(ValidationError):
        CouponWrite(
            code="VIP20",
            discount_percent=101,
            service_ids=[service_id],
            vehicle_types=["sedan"],
        )
    with pytest.raises(ValidationError, match="only once"):
        CouponWrite(
            code="VIP20",
            discount_percent=20,
            service_ids=[service_id, service_id],
            vehicle_types=["sedan"],
        )


@pytest.mark.parametrize(
    ("price", "percent", "discount"),
    [(13_500, 20, 2_700), (7_300, 15, 1_095), (101, 50, 51), (13_500, 100, 13_500)],
)
def test_percentage_discount_uses_integer_minor_units(
    price: int, percent: int, discount: int
) -> None:
    assert percentage_discount(price, percent) == discount


@pytest.mark.asyncio
async def test_eligible_coupon_applies_only_to_selected_service_line() -> None:
    service_id = uuid.uuid4()
    other_service_id = uuid.uuid4()
    lines = [
        _line(position=1, service_id=service_id, make="Toyota", model="Camry"),
        _line(position=2, service_id=service_id, make="Nissan", model="Patrol"),
        _line(position=3, service_id=other_service_id, make="BMW", model="X5"),
    ]
    session = _coupon_session(service_id, lines, discount_percent=20)
    preview = await resolve_coupon(
        session,
        business_id=uuid.uuid4(),
        currency_code="AED",
        code="VIP20",
        lines=lines,
        selected_line_position=None,
    )
    assert preview.selected_line_position is None
    assert [line.position for line in preview.eligible_lines] == [1, 2]
    assert preview.discount_minor == 0

    session = _coupon_session(service_id, lines, discount_percent=20)
    applied = await resolve_coupon(
        session,
        business_id=uuid.uuid4(),
        currency_code="AED",
        code="VIP20",
        lines=lines,
        selected_line_position=2,
    )
    assert applied.selected_line_position == 2
    assert applied.discount_minor == 2_700
    assert 13_500 * len(lines) - applied.discount_minor == 37_800


@pytest.mark.asyncio
async def test_single_eligible_coupon_line_is_selected_automatically() -> None:
    service_id = uuid.uuid4()
    lines = [_line(service_id=service_id)]
    result = await resolve_coupon(
        _coupon_session(service_id, lines),
        business_id=uuid.uuid4(),
        currency_code="AED",
        code="VIP20",
        lines=lines,
        selected_line_position=None,
    )
    assert result.selected_line_position == 1
    assert result.discount_minor == 2_700


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "code"),
    [
        ("inactive", "COUPON_INVALID"),
        ("minimum", "COUPON_MINIMUM_VEHICLES"),
        ("service", "COUPON_SERVICE_INELIGIBLE"),
        ("vehicle", "COUPON_VEHICLE_INELIGIBLE"),
        ("loyalty", "COUPON_LOYALTY_CONFLICT"),
    ],
)
async def test_coupon_rejects_invalid_conditions(mode: str, code: str) -> None:
    eligible_service = uuid.uuid4()
    line = _line(
        service_id=uuid.uuid4() if mode == "service" else eligible_service,
        vehicle_type="suv" if mode == "vehicle" else "sedan",
        loyalty_reward_id=uuid.uuid4() if mode == "loyalty" else None,
    )
    session = _coupon_session(
        eligible_service,
        [line],
        minimum_vehicle_count=2 if mode == "minimum" else None,
        active=mode != "inactive",
    )
    with pytest.raises(DomainError) as raised:
        await resolve_coupon(
            session,
            business_id=uuid.uuid4(),
            currency_code="AED",
            code="VIP20",
            lines=[line],
            selected_line_position=1,
        )
    assert raised.value.code == code


def test_booking_snapshot_keeps_coupon_values_after_configuration_changes() -> None:
    booking_id = uuid.uuid4()
    vehicle = BookingVehicle(
        id=uuid.uuid4(),
        booking_id=booking_id,
        position=1,
        make="BMW",
        model="X5",
        vehicle_type="suv",
    )
    service = BookingService(
        booking_id=booking_id,
        booking_vehicle_id=vehicle.id,
        service_id=uuid.uuid4(),
        service_name="Premium Wash",
        unit_price_minor=13_500,
        list_price_minor=13_500,
        discount_minor=2_700,
        discount_type="coupon",
        coupon_code_snapshot="PREM20",
        discount_percent_snapshot=20,
        quantity=1,
        line_total_minor=10_800,
        expected_duration_minutes=120,
    )
    summary = vehicle_summaries_from_rows([(vehicle, service, None)])[booking_id][0]
    assert summary.discount_type == "coupon"
    assert summary.coupon_code == "PREM20"
    assert summary.discount_percent == 20
    assert summary.line_total_minor == 10_800


def test_coupon_manager_api_rejects_employee_and_accepts_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock()
    app.dependency_overrides[session_dependency] = lambda: session
    app.dependency_overrides[staff_context] = lambda: _context(StaffRole.EMPLOYEE)
    try:
        with TestClient(app) as client:
            forbidden = client.get("/api/v1/staff/coupons")
        assert forbidden.status_code == 403
    finally:
        app.dependency_overrides.clear()

    manager = _context(StaffRole.MANAGER)
    list_mock = AsyncMock(return_value=CouponList(coupons=[]))
    monkeypatch.setattr(staff_api, "list_coupons", list_mock)
    app.dependency_overrides[session_dependency] = lambda: session
    app.dependency_overrides[staff_context] = lambda: manager
    try:
        with TestClient(app) as client:
            allowed = client.get("/api/v1/staff/coupons")
        assert allowed.status_code == 200
        assert allowed.json() == {"coupons": []}
        assert list_mock.await_args.args == (session, manager)
    finally:
        app.dependency_overrides.clear()


def test_coupon_migration_is_private_constrained_child_of_current_head() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations/versions/bb30898caab6_add_coupon_codes.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "f6c28a4e1b73"' in migration
    assert "uq_coupon_business_code" in migration
    assert "^[A-Z0-9]{3,6}$" in migration
    assert "discount_percent BETWEEN 1 AND 100" in migration
    assert "booking_service_discount_type" in migration
    assert "uq_booking_services_booking_coupon" in migration
    assert "'loyalty_reward','coupon'" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL" in migration


def _line(
    *,
    position: int = 1,
    service_id: uuid.UUID | None = None,
    vehicle_type: str = "sedan",
    make: str = "Toyota",
    model: str = "Camry",
    loyalty_reward_id: uuid.UUID | None = None,
) -> CouponCheckoutLine:
    return CouponCheckoutLine.model_validate(
        {
            "position": position,
            "service_id": service_id or uuid.uuid4(),
            "vehicle_type": vehicle_type,
            "make": make,
            "model": model,
            "loyalty_reward_id": loyalty_reward_id,
        }
    )


def _coupon_session(
    eligible_service_id: uuid.UUID,
    lines: list[CouponCheckoutLine],
    *,
    discount_percent: int = 20,
    minimum_vehicle_count: int | None = None,
    active: bool = True,
) -> MagicMock:
    coupon_id = uuid.uuid4()
    coupon = Coupon(
        id=coupon_id,
        business_id=uuid.uuid4(),
        code="VIP20",
        discount_percent=discount_percent,
        minimum_vehicle_count=minimum_vehicle_count,
        is_active=True,
        created_by_staff_id=uuid.uuid4(),
    )
    services = {
        line.service_id: Service(
            id=line.service_id,
            business_id=uuid.uuid4(),
            name="Premium Wash",
            price_minor=13_500,
            estimated_duration_minutes=120,
        )
        for line in lines
    }
    prices = [
        ServicePrice(
            id=uuid.uuid4(),
            business_id=uuid.uuid4(),
            service_id=line.service_id,
            vehicle_type=line.vehicle_type,
            price_minor=13_500,
        )
        for line in lines
    ]
    session = MagicMock()
    session.scalar = AsyncMock(return_value=coupon if active else None)
    session.scalars = AsyncMock(
        side_effect=[
            Rows([eligible_service_id]),
            Rows(["sedan"]),
            Rows(list(services.values())),
            Rows(prices),
        ]
    )
    return session


def _context(role: StaffRole) -> StaffContext:
    return StaffContext(
        auth_user_id=uuid.uuid4(),
        staff_id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        business_name="Trifecta",
        role=role,
        timezone="Asia/Dubai",
    )

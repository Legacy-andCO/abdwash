import uuid
from datetime import date, time
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.auth.dependencies import StaffContext
from app.domain.enums import StaffRole
from app.domain.errors import ConflictError
from app.models.entities import (
    BookingService,
    BookingServiceAddon,
    BookingVehicle,
    Business,
    BusinessOperatingHour,
    BusinessSettings,
    Service,
    ServiceAddon,
    ServicePrice,
)
from app.schemas.catalogue import (
    BusinessBookingSettingsPatch,
    OperatingHourInput,
    ServiceInput,
    ServicePatch,
)
from app.schemas.public import BookingCreate
from app.services.booking_snapshots import vehicle_summaries_from_rows
from app.services.catalogue import get_catalogue
from app.services.scheduling import policy_for_day
from app.services.service_catalogue import update_service
from tests.test_public_schemas import valid_booking_payload


def service_input(**updates: object) -> ServiceInput:
    payload: dict[str, object] = {
        "name": "Standard Wash",
        "description": "Exterior and interior",
        "default_duration_minutes": 90,
        "mobile_available": True,
        "shop_available": True,
        "prices": [
            {"vehicle_type": "sedan", "price_minor": 8500},
            {"vehicle_type": "suv", "price_minor": 10500},
        ],
    }
    payload.update(updates)
    return ServiceInput.model_validate(payload)


def test_service_schema_keeps_integer_minor_unit_prices_and_duration() -> None:
    request = service_input()
    assert request.prices[0].price_minor == 8500
    assert request.default_duration_minutes == 90


def test_service_schema_rejects_duplicate_vehicle_prices() -> None:
    with pytest.raises(ValidationError, match="only one price"):
        service_input(
            prices=[
                {"vehicle_type": "sedan", "price_minor": 8500},
                {"vehicle_type": "sedan", "price_minor": 9000},
            ]
        )


def test_service_schema_requires_a_delivery_channel() -> None:
    with pytest.raises(ValidationError, match="Mobile, Shop"):
        service_input(mobile_available=False, shop_available=False)


@pytest.mark.parametrize("minutes", [14, 1441])
def test_service_schema_bounds_default_duration(minutes: int) -> None:
    with pytest.raises(ValidationError):
        service_input(default_duration_minutes=minutes)


def test_business_settings_accept_only_controlled_slot_durations() -> None:
    assert BusinessBookingSettingsPatch(slot_duration_minutes=90).slot_duration_minutes == 90
    with pytest.raises(ValidationError):
        BusinessBookingSettingsPatch(slot_duration_minutes=75)


def test_typed_patch_schemas_reject_null_for_required_database_fields() -> None:
    with pytest.raises(ValidationError, match="cannot be null"):
        ServicePatch(name=None)
    with pytest.raises(ValidationError, match="cannot be null"):
        BusinessBookingSettingsPatch(slot_duration_minutes=None)


def test_business_settings_require_each_weekday_exactly_once() -> None:
    repeated = [
        OperatingHourInput(
            weekday=0,
            is_open=True,
            opening_time=time(8),
            closing_time=time(18),
        )
        for _ in range(7)
    ]
    with pytest.raises(ValidationError, match="each weekday exactly once"):
        BusinessBookingSettingsPatch(operating_hours=repeated)


def test_booking_vehicle_accepts_unique_addons_and_rejects_duplicates() -> None:
    addon_id = str(uuid.uuid4())
    payload = valid_booking_payload()
    payload["vehicles"][0]["addon_ids"] = [addon_id]  # type: ignore[index]
    request = BookingCreate.model_validate(payload)
    assert request.vehicles[0].addon_ids == [uuid.UUID(addon_id)]
    payload["vehicles"][0]["addon_ids"] = [addon_id, addon_id]  # type: ignore[index]
    with pytest.raises(ValidationError, match="selected only once"):
        BookingCreate.model_validate(payload)


@pytest.mark.asyncio
async def test_public_catalogue_loads_prices_and_addons_in_two_bounded_queries() -> None:
    business_id = uuid.uuid4()
    service_id = uuid.uuid4()
    business = Business(id=business_id, name="Trifecta", slug="trifecta", is_active=True)
    settings = BusinessSettings(
        id=uuid.uuid4(),
        business_id=business_id,
        timezone="Asia/Dubai",
        currency_code="AED",
        opening_time=time(8),
        closing_time=time(18),
        slot_duration_minutes=120,
        multi_vehicle_threshold=3,
        multi_vehicle_required_slots=2,
        cancellation_cutoff_hours=24,
        hold_duration_minutes=10,
        mobile_minimum_enabled=False,
        mobile_minimum_minor=0,
    )
    service = Service(
        id=service_id,
        business_id=business_id,
        name="Standard Wash",
        description=None,
        price_minor=8500,
        estimated_duration_minutes=90,
        is_active=True,
        mobile_available=True,
        shop_available=True,
        sort_order=0,
    )
    price = ServicePrice(
        id=uuid.uuid4(),
        business_id=business_id,
        service_id=service_id,
        vehicle_type="sedan",
        price_minor=8500,
    )
    addon = ServiceAddon(
        id=uuid.uuid4(),
        business_id=business_id,
        service_id=service_id,
        name="Pet hair removal",
        description=None,
        price_minor=2500,
        default_duration_minutes=20,
        mobile_available=True,
        shop_available=True,
        is_active=True,
        sort_order=0,
    )
    configuration_result = MagicMock()
    configuration_result.one_or_none.return_value = (business, settings)
    catalogue_result = MagicMock()
    # A joined price/add-on row can repeat; the serializer must de-duplicate it.
    catalogue_result.all.return_value = [(service, price, addon), (service, price, addon)]
    session = AsyncMock()
    session.execute.side_effect = [configuration_result, catalogue_result]

    result = await get_catalogue(session)

    assert session.execute.await_count == 2
    assert result.services[0].prices[0].price_minor == 8500
    assert [item.name for item in result.services[0].addons] == ["Pet hair removal"]


@pytest.mark.asyncio
async def test_closed_operating_day_returns_no_schedule_policy() -> None:
    business_id = uuid.uuid4()
    settings = BusinessSettings(
        business_id=business_id,
        opening_time=time(8),
        closing_time=time(18),
        slot_duration_minutes=120,
        multi_vehicle_threshold=3,
        multi_vehicle_required_slots=2,
        hold_duration_minutes=10,
    )
    session = AsyncMock()
    session.scalar.return_value = BusinessOperatingHour(
        business_id=business_id,
        weekday=0,
        is_open=False,
        opening_time=None,
        closing_time=None,
    )
    assert await policy_for_day(session, settings, date(2026, 8, 24)) is None


@pytest.mark.asyncio
async def test_loyalty_reward_service_cannot_be_deactivated_until_replaced() -> None:
    business_id = uuid.uuid4()
    service_id = uuid.uuid4()
    service = Service(
        id=service_id,
        business_id=business_id,
        name="Standard Wash",
        price_minor=8500,
        estimated_duration_minutes=90,
        mobile_available=True,
        shop_available=True,
        is_active=True,
        sort_order=0,
    )
    context = StaffContext(
        auth_user_id=uuid.uuid4(),
        staff_id=uuid.uuid4(),
        business_id=business_id,
        business_name="Trifecta",
        role=StaffRole.MANAGER,
        timezone="Asia/Dubai",
    )
    session = AsyncMock()
    session.scalar.side_effect = [service, service_id]
    with pytest.raises(ConflictError) as caught:
        await update_service(session, context, service_id, ServicePatch(is_active=False))
    assert caught.value.code == "LOYALTY_REWARD_SERVICE_ACTIVE"


def test_new_tables_preserve_tenant_and_snapshot_constraints() -> None:
    migration = (
        __import__("pathlib").Path(__file__).parents[1]
        / "migrations/versions/9d5f551c26e5_add_service_catalogue_management.py"
    ).read_text(encoding="utf-8")
    assert "business_id" in migration
    assert "booking_service_addons" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL" in migration
    assert "UPDATE booking_services snapshot" in migration


def test_historical_service_and_addon_snapshots_render_without_live_catalogue_reads() -> None:
    booking_id = uuid.uuid4()
    vehicle = BookingVehicle(
        id=uuid.uuid4(),
        booking_id=booking_id,
        position=1,
        make="Toyota",
        model="Camry",
        vehicle_type="sedan",
    )
    service = BookingService(
        booking_id=booking_id,
        booking_vehicle_id=vehicle.id,
        service_id=uuid.uuid4(),
        service_name="Original Service Name",
        unit_price_minor=8500,
        list_price_minor=8500,
        discount_minor=0,
        quantity=1,
        line_total_minor=8500,
        expected_duration_minutes=90,
    )
    addon = BookingServiceAddon(
        booking_id=booking_id,
        booking_vehicle_id=vehicle.id,
        service_addon_id=uuid.uuid4(),
        addon_name="Original Add-on Name",
        unit_price_minor=2500,
        expected_duration_minutes=20,
    )

    summary = vehicle_summaries_from_rows([(vehicle, service, addon)])[booking_id][0]

    assert summary.service_name == "Original Service Name"
    assert summary.addons[0].name == "Original Add-on Name"
    assert summary.line_total_minor == 11_000
    assert summary.expected_duration_minutes == 90


def test_seed_backfills_missing_prices_without_overwriting_owner_catalogue() -> None:
    seed = (
        __import__("pathlib").Path(__file__).parents[1] / "app/cli/seed.py"
    ).read_text(encoding="utf-8")
    assert "if service is None:" in seed
    assert "if not price_count:" in seed
    assert "service.name =" not in seed
    assert "service.price_minor =" not in seed

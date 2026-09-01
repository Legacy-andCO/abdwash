import asyncio
from datetime import time

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.domain.catalogue import VEHICLE_TYPES
from app.domain.timezones import TRIFECTA_TIMEZONE
from app.models.entities import (
    Business,
    BusinessOperatingHour,
    BusinessSettings,
    InventoryLocation,
    ScheduleResource,
    Service,
    ServicePrice,
)


async def seed() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            business = (
                await session.scalars(select(Business).where(Business.slug == "abdwash"))
            ).one_or_none()
            if business is None:
                business = Business(name="Trifecta", slug="abdwash", is_active=True)
                session.add(business)
                await session.flush()
            elif business.name != "Trifecta":
                business.name = "Trifecta"
            main_locations = list(
                await session.scalars(
                    select(InventoryLocation).where(
                        InventoryLocation.business_id == business.id,
                        InventoryLocation.location_type == "main",
                        InventoryLocation.is_active.is_(True),
                    )
                )
            )
            main_location = main_locations[0] if len(main_locations) == 1 else None
            if not main_locations:
                main_shop_name_taken = await session.scalar(
                    select(InventoryLocation.id).where(
                        InventoryLocation.business_id == business.id,
                        func.lower(InventoryLocation.name) == "main shop",
                    )
                )
                main_location = InventoryLocation(
                    business_id=business.id,
                    name="Main Shop (Primary)" if main_shop_name_taken else "Main Shop",
                    location_type="main",
                    is_active=True,
                )
                session.add(main_location)
                await session.flush()
            business_settings = (
                await session.scalars(
                    select(BusinessSettings).where(BusinessSettings.business_id == business.id)
                )
            ).one_or_none()
            if business_settings is None:
                business_settings = BusinessSettings(
                    business_id=business.id,
                    timezone=TRIFECTA_TIMEZONE,
                    currency_code="AED",
                    opening_time=time(9),
                    closing_time=time(21),
                    slot_duration_minutes=120,
                    multi_vehicle_threshold=3,
                    multi_vehicle_required_slots=2,
                    cancellation_cutoff_hours=24,
                    hold_duration_minutes=10,
                )
                session.add(business_settings)
                await session.flush()
            if (
                business_settings.default_inventory_location_id is None
                and main_location is not None
            ):
                business_settings.default_inventory_location_id = main_location.id
            operating_hours = set(
                (
                    await session.scalars(
                        select(BusinessOperatingHour.weekday).where(
                            BusinessOperatingHour.business_id == business.id
                        )
                    )
                ).all()
            )
            for weekday in range(7):
                if weekday not in operating_hours:
                    session.add(
                        BusinessOperatingHour(
                            business_id=business.id,
                            weekday=weekday,
                            is_open=True,
                            opening_time=business_settings.opening_time,
                            closing_time=business_settings.closing_time,
                        )
                    )
            team = (
                await session.scalars(
                    select(ScheduleResource).where(
                        ScheduleResource.business_id == business.id,
                        ScheduleResource.name == "Mobile Team 1",
                    )
                )
            ).one_or_none()
            if team is None:
                session.add(
                    ScheduleResource(
                        business_id=business.id,
                        name="Mobile Team 1",
                        resource_type="mobile_team",
                        is_active=True,
                        sort_order=1,
                    )
                )
            bootstrap_service = (
                await session.scalars(
                    select(Service).where(
                        Service.business_id == business.id,
                        Service.name == "Development Standard Wash",
                    )
                )
            ).one_or_none()
            if bootstrap_service is not None:
                bootstrap_service.is_active = False

            service_seed = [
                (
                    "Standard Wash",
                    "Complete mobile wash for regular vehicle care.",
                    7300,
                    8600,
                    120,
                    1,
                    "single_service",
                    True,
                    [
                        "Exterior Power Wash",
                        "Hard Wash",
                        "Tires & Rims Clean & Shine",
                        "Interior Vacuum",
                        "Interior Dusting",
                        "Interior Wipe Down",
                        "Interior Windows Cleaning",
                    ],
                ),
                (
                    "Gold Wash",
                    "More complete exterior and interior care with finishing touches.",
                    9300,
                    10500,
                    150,
                    2,
                    "single_service",
                    True,
                    [
                        "Exterior Power Wash",
                        "Foam Wash",
                        "Hard Wash",
                        "Tires & Rims Clean & Shine",
                        "Underbody Rinse",
                        "Interior Vacuum",
                        "Interior Dusting",
                        "Interior Wipe Down",
                        "Interior Windows Cleaning",
                        "Dashboard Shine",
                        "Protective Plastic Covers for Mat & Steering Wheel",
                        "Air Freshener",
                    ],
                ),
                (
                    "Premium Wash",
                    "Premium exterior, engine, wheel and interior care.",
                    12500,
                    13500,
                    180,
                    3,
                    "single_service",
                    True,
                    [
                        "Exterior Power Wash",
                        "Foam Wash",
                        "Hard Wash",
                        "Tires & Rims Clean & Shine",
                        "Underbody Rinse",
                        "Spray Wax Application",
                        "Engine Cleaning & Protection",
                        "Wheel Chemical Cleaning",
                        "Interior Vacuum",
                        "Interior Dusting",
                        "Interior Wipe Down",
                        "Interior Windows Cleaning",
                        "Dashboard Shine",
                        "Protective Plastic Covers for Mat & Steering Wheel",
                        "Air Freshener",
                    ],
                ),
                (
                    "Monthly Package",
                    "Once weekly. Monthly package; online entitlement activation "
                    "is not yet available.",
                    26000,
                    37000,
                    120,
                    4,
                    "monthly_package",
                    False,
                    [
                        "Once weekly",
                        "Exterior Power Wash",
                        "Hard Wash",
                        "Tires & Rims Clean & Shine",
                        "Interior Vacuum",
                        "Interior Dusting",
                        "Interior Wipe Down",
                        "Interior Windows Cleaning",
                    ],
                ),
                (
                    "Interior Deep Cleaning",
                    "A complete interior reset for upholstery, leather and difficult stains.",
                    35000,
                    42000,
                    240,
                    5,
                    "single_service",
                    True,
                    [
                        "Full Interior Deep Cleaning",
                        "Shampooing",
                        "Stain Removal",
                        "Leather Deep Cleaning",
                    ],
                ),
                (
                    "Exterior Polishing",
                    "Exterior polishing, wax and paint enhancement.",
                    40000,
                    52000,
                    240,
                    6,
                    "single_service",
                    True,
                    ["Full Exterior Polishing", "Wax", "Paint Enhancement"],
                ),
            ]
            existing_services = {
                service.name: service
                for service in (
                    await session.scalars(
                        select(Service).where(
                            Service.business_id == business.id,
                            Service.name.in_([item[0] for item in service_seed]),
                        )
                    )
                ).all()
            }
            for (
                name,
                description,
                car_price,
                suv_price,
                duration,
                sort_order,
                kind,
                bookable,
                features,
            ) in service_seed:
                service = existing_services.get(name)
                if service is None:
                    service = Service(
                        business_id=business.id,
                        name=name,
                        description=description,
                        price_minor=car_price,
                        estimated_duration_minutes=duration,
                        is_active=True,
                        sort_order=sort_order,
                        checklist_template=[{"label": item, "required": True} for item in features],
                        included_features=features,
                        product_kind=kind,
                        customer_bookable=bookable,
                    )
                    session.add(service)
                    await session.flush()
                price_count = await session.scalar(
                    select(func.count(ServicePrice.id)).where(ServicePrice.service_id == service.id)
                )
                if not price_count:
                    session.add_all(
                        [
                            ServicePrice(
                                business_id=business.id,
                                service_id=service.id,
                                vehicle_type=vehicle_type,
                                price_minor=(
                                    suv_price
                                    if vehicle_type in {"suv", "pickup", "van"}
                                    else car_price
                                ),
                            )
                            for vehicle_type in VEHICLE_TYPES
                        ]
                    )
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()

import asyncio
from datetime import time

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.models.entities import (
    Business,
    BusinessSettings,
    InventoryLocation,
    ScheduleResource,
    Service,
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
            main_location = (
                await session.scalars(
                    select(InventoryLocation).where(
                        InventoryLocation.business_id == business.id,
                        InventoryLocation.location_type == "main",
                        InventoryLocation.is_active.is_(True),
                    )
                )
            ).first()
            if main_location is None:
                main_shop_name_taken = await session.scalar(
                    select(InventoryLocation.id).where(
                        InventoryLocation.business_id == business.id,
                        func.lower(InventoryLocation.name) == "main shop",
                    )
                )
                session.add(
                    InventoryLocation(
                        business_id=business.id,
                        name="Main Shop (Primary)" if main_shop_name_taken else "Main Shop",
                        location_type="main",
                        is_active=True,
                    )
                )
            business_settings = (
                await session.scalars(
                    select(BusinessSettings).where(BusinessSettings.business_id == business.id)
                )
            ).one_or_none()
            if business_settings is None:
                session.add(
                    BusinessSettings(
                        business_id=business.id,
                        timezone="Asia/Dubai",
                        currency_code="AED",
                        opening_time=time(9),
                        closing_time=time(21),
                        slot_duration_minutes=120,
                        multi_vehicle_threshold=3,
                        multi_vehicle_required_slots=2,
                        cancellation_cutoff_hours=24,
                        hold_duration_minutes=10,
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
                    "Express Exterior",
                    "A careful exterior wash, wheel clean, and hand-finished dry.",
                    8500,
                    90,
                    1,
                    [
                        {"label": "Exterior wash", "required": True},
                        {"label": "Wheels and tyres", "required": True},
                        {"label": "Exterior glass", "required": True},
                        {"label": "Hand-finished dry", "required": True},
                        {"label": "Final inspection", "required": True},
                    ],
                ),
                (
                    "Signature Inside & Out",
                    "Complete exterior care with a considered interior refresh.",
                    14500,
                    120,
                    2,
                    [
                        {"label": "Exterior wash", "required": True},
                        {"label": "Wheels and tyres", "required": True},
                        {"label": "Exterior and interior glass", "required": True},
                        {"label": "Interior vacuum", "required": True},
                        {"label": "Dashboard and interior wipe", "required": True},
                        {"label": "Final inspection", "required": True},
                    ],
                ),
                (
                    "Premium Detail",
                    "Our most thorough reset for a car that deserves extra attention.",
                    22000,
                    180,
                    3,
                    [
                        {"label": "Pre-wash inspection", "required": True},
                        {"label": "Exterior wash and decontamination", "required": True},
                        {"label": "Wheels and tyres", "required": True},
                        {"label": "Exterior and interior glass", "required": True},
                        {"label": "Interior vacuum", "required": True},
                        {"label": "Detailed interior wipe", "required": True},
                        {"label": "Finishing treatment", "required": True},
                        {"label": "Final inspection", "required": True},
                    ],
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
            for name, description, price, duration, sort_order, checklist in service_seed:
                service = existing_services.get(name)
                if service is None:
                    session.add(
                        Service(
                            business_id=business.id,
                            name=name,
                            description=description,
                            price_minor=price,
                            estimated_duration_minutes=duration,
                            is_active=True,
                            sort_order=sort_order,
                            checklist_template=checklist,
                        )
                    )
                else:
                    service.description = description
                    service.price_minor = price
                    service.estimated_duration_minutes = duration
                    service.is_active = True
                    service.sort_order = sort_order
                    service.checklist_template = checklist
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()

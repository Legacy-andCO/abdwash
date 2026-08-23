import asyncio
from datetime import time

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.models.entities import Business, BusinessSettings, ScheduleResource, Service


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
                business = Business(name="AbdWash", slug="abdwash", is_active=True)
                session.add(business)
                await session.flush()
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
                ),
                (
                    "Signature Inside & Out",
                    "Complete exterior care with a considered interior refresh.",
                    14500,
                    120,
                    2,
                ),
                (
                    "Premium Detail",
                    "Our most thorough reset for a car that deserves extra attention.",
                    22000,
                    180,
                    3,
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
            for name, description, price, duration, sort_order in service_seed:
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
                        )
                    )
                else:
                    service.description = description
                    service.price_minor = price
                    service.estimated_duration_minutes = duration
                    service.is_active = True
                    service.sort_order = sort_order
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()

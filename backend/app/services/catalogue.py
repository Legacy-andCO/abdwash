from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.business import load_active_services, load_default_business
from app.schemas.public import CatalogueResponse, SafeBusinessSettings, ServicePublic


async def get_catalogue(session: AsyncSession) -> CatalogueResponse:
    configuration = await load_default_business(session)
    services = await load_active_services(session, configuration.business.id)
    settings = configuration.settings
    return CatalogueResponse(
        business_name=configuration.business.name,
        settings=SafeBusinessSettings(
            timezone=settings.timezone,
            currency_code=settings.currency_code,
            opening_time=settings.opening_time,
            closing_time=settings.closing_time,
            slot_duration_minutes=settings.slot_duration_minutes,
            multi_vehicle_threshold=settings.multi_vehicle_threshold,
            multi_vehicle_required_slots=settings.multi_vehicle_required_slots,
            hold_duration_minutes=settings.hold_duration_minutes,
            cancellation_cutoff_hours=settings.cancellation_cutoff_hours,
        ),
        services=[
            ServicePublic(
                id=service.id,
                name=service.name,
                description=service.description,
                price_minor=service.price_minor,
                currency_code=settings.currency_code,
                estimated_duration_minutes=service.estimated_duration_minutes,
            )
            for service in services
        ],
    )

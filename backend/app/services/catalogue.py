from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Service, ServiceAddon, ServicePrice
from app.repositories.business import load_default_business
from app.schemas.public import (
    CatalogueResponse,
    SafeBusinessSettings,
    ServiceAddonPublic,
    ServicePricePublic,
    ServicePublic,
)


async def get_catalogue(session: AsyncSession) -> CatalogueResponse:
    configuration = await load_default_business(session)
    settings = configuration.settings
    rows = (
        await session.execute(
            select(Service, ServicePrice, ServiceAddon)
            .select_from(Service)
            .outerjoin(
                ServicePrice,
                (ServicePrice.service_id == Service.id)
                & (ServicePrice.business_id == configuration.business.id),
            )
            .outerjoin(
                ServiceAddon,
                (ServiceAddon.service_id == Service.id)
                & (ServiceAddon.business_id == configuration.business.id)
                & ServiceAddon.is_active.is_(True)
                & ServiceAddon.mobile_available.is_(True),
            )
            .where(
                Service.business_id == configuration.business.id,
                Service.is_active.is_(True),
                Service.mobile_available.is_(True),
            )
            .order_by(
                Service.sort_order,
                Service.name,
                ServicePrice.vehicle_type,
                ServiceAddon.sort_order,
                ServiceAddon.name,
            )
        )
    ).all()
    services: dict[object, Service] = {}
    prices: dict[object, list[ServicePricePublic]] = defaultdict(list)
    addons: dict[object, list[ServiceAddonPublic]] = defaultdict(list)
    seen_prices: set[tuple[object, str]] = set()
    seen_addons: set[object] = set()
    for service, price, addon in rows:
        services.setdefault(service.id, service)
        if price is not None and (price.service_id, price.vehicle_type) not in seen_prices:
            seen_prices.add((price.service_id, price.vehicle_type))
            prices[price.service_id].append(
                ServicePricePublic(
                    vehicle_type=price.vehicle_type,
                    price_minor=price.price_minor,
                )
            )
        if addon is not None and addon.id not in seen_addons:
            seen_addons.add(addon.id)
            addons[addon.service_id].append(
                ServiceAddonPublic(
                    id=addon.id,
                    name=addon.name,
                    description=addon.description,
                    price_minor=addon.price_minor,
                    currency_code=settings.currency_code,
                    default_duration_minutes=addon.default_duration_minutes,
                    mobile_available=addon.mobile_available,
                    shop_available=addon.shop_available,
                )
            )
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
            mobile_minimum_enabled=settings.mobile_minimum_enabled,
            mobile_minimum_minor=settings.mobile_minimum_minor,
        ),
        services=[
            ServicePublic(
                id=service.id,
                name=service.name,
                description=service.description,
                price_minor=service.price_minor,
                currency_code=settings.currency_code,
                estimated_duration_minutes=service.estimated_duration_minutes,
                mobile_available=service.mobile_available,
                shop_available=service.shop_available,
                prices=prices[service.id],
                addons=addons[service.id],
            )
            for service in services.values()
        ],
    )

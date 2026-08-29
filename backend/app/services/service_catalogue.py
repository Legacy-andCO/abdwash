import uuid
from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import StaffContext
from app.domain.catalogue import VEHICLE_TYPES
from app.domain.errors import ConflictError, DomainError
from app.models.entities import (
    AuditEvent,
    BusinessOperatingHour,
    BusinessSettings,
    InventoryLocation,
    Service,
    ServiceAddon,
    ServicePrice,
)
from app.schemas.catalogue import (
    AddonInput,
    AddonPatch,
    AddonView,
    BusinessBookingSettingsPatch,
    BusinessBookingSettingsView,
    CatalogueManagementView,
    OperatingHourView,
    ServiceInput,
    ServiceManagementView,
    ServicePatch,
    VehiclePriceInput,
    VehiclePriceView,
)


def _audit(
    session: AsyncSession,
    context: StaffContext,
    event_type: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
) -> None:
    session.add(
        AuditEvent(
            business_id=context.business_id,
            actor_auth_user_id=context.auth_user_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json={},
        )
    )


async def _service_or_404(
    session: AsyncSession, business_id: uuid.UUID, service_id: uuid.UUID, *, lock: bool = False
) -> Service:
    statement = select(Service).where(Service.id == service_id, Service.business_id == business_id)
    if lock:
        statement = statement.with_for_update()
    service = await session.scalar(statement)
    if service is None:
        raise DomainError("SERVICE_NOT_FOUND", "Service not found.", status_code=404)
    return service


async def list_managed_catalogue(
    session: AsyncSession, context: StaffContext
) -> CatalogueManagementView:
    settings = await session.scalar(
        select(BusinessSettings).where(BusinessSettings.business_id == context.business_id)
    )
    if settings is None:
        raise DomainError(
            "BUSINESS_SETTINGS_NOT_FOUND",
            "Business settings are unavailable.",
            status_code=404,
        )
    rows = (
        await session.execute(
            select(Service, ServicePrice, ServiceAddon)
            .select_from(Service)
            .outerjoin(
                ServicePrice,
                (ServicePrice.service_id == Service.id)
                & (ServicePrice.business_id == context.business_id),
            )
            .outerjoin(
                ServiceAddon,
                (ServiceAddon.service_id == Service.id)
                & (ServiceAddon.business_id == context.business_id),
            )
            .where(Service.business_id == context.business_id)
            .order_by(
                Service.sort_order,
                Service.name,
                ServicePrice.vehicle_type,
                ServiceAddon.sort_order,
                ServiceAddon.name,
            )
        )
    ).all()
    services: dict[uuid.UUID, Service] = {}
    prices: dict[uuid.UUID, list[VehiclePriceView]] = defaultdict(list)
    addons: dict[uuid.UUID, list[AddonView]] = defaultdict(list)
    seen_prices: set[tuple[uuid.UUID, str]] = set()
    seen_addons: set[uuid.UUID] = set()
    for service, price, addon in rows:
        services.setdefault(service.id, service)
        if price is not None and (price.service_id, price.vehicle_type) not in seen_prices:
            seen_prices.add((price.service_id, price.vehicle_type))
            prices[price.service_id].append(
                VehiclePriceView(
                    vehicle_type=price.vehicle_type,
                    price_minor=price.price_minor,
                )
            )
        if addon is not None and addon.id not in seen_addons:
            seen_addons.add(addon.id)
            addons[addon.service_id].append(_addon_view(addon))
    return CatalogueManagementView(
        currency_code=settings.currency_code,
        vehicle_types=list(VEHICLE_TYPES),
        services=[
            _service_view(service, prices[service.id], addons[service.id])
            for service in services.values()
        ],
    )


async def create_service(
    session: AsyncSession, context: StaffContext, request: ServiceInput
) -> ServiceManagementView:
    service = Service(
        business_id=context.business_id,
        name=request.name.strip(),
        description=request.description.strip() if request.description else None,
        price_minor=min(item.price_minor for item in request.prices),
        estimated_duration_minutes=request.default_duration_minutes,
        mobile_available=request.mobile_available,
        shop_available=request.shop_available,
        is_active=request.is_active,
        sort_order=request.sort_order,
    )
    session.add(service)
    await session.flush()
    prices = await _replace_prices(session, context.business_id, service, request.prices)
    _audit(session, context, "service_created", "service", service.id)
    return _service_view(service, prices, [])


async def update_service(
    session: AsyncSession,
    context: StaffContext,
    service_id: uuid.UUID,
    request: ServicePatch,
) -> ServiceManagementView:
    service = await _service_or_404(session, context.business_id, service_id, lock=True)
    values = request.model_dump(exclude_unset=True, exclude={"prices"})
    if values.get("is_active") is False and service.is_active:
        reward_service_id = await session.scalar(
            select(BusinessSettings.loyalty_reward_service_id).where(
                BusinessSettings.business_id == context.business_id
            )
        )
        if reward_service_id == service.id:
            raise ConflictError(
                "LOYALTY_REWARD_SERVICE_ACTIVE",
                "Choose another loyalty reward service before deactivating this service.",
            )
    resulting_mobile = values.get("mobile_available", service.mobile_available)
    resulting_shop = values.get("shop_available", service.shop_available)
    if not resulting_mobile and not resulting_shop:
        raise DomainError("SERVICE_CHANNEL_REQUIRED", "Select Mobile, Shop, or both.")
    if "default_duration_minutes" in values:
        service.estimated_duration_minutes = values.pop("default_duration_minutes")
    for key, value in values.items():
        if key in {"name", "description"} and isinstance(value, str):
            value = value.strip() or None
        setattr(service, key, value)
    if request.prices is None:
        price_rows = list(
            (
                await session.scalars(
                    select(ServicePrice)
                    .where(ServicePrice.service_id == service.id)
                    .order_by(ServicePrice.vehicle_type)
                )
            ).all()
        )
        prices = [
            VehiclePriceView(vehicle_type=row.vehicle_type, price_minor=row.price_minor)
            for row in price_rows
        ]
    else:
        prices = await _replace_prices(session, context.business_id, service, request.prices)
    addon_rows = list(
        (
            await session.scalars(
                select(ServiceAddon)
                .where(
                    ServiceAddon.business_id == context.business_id,
                    ServiceAddon.service_id == service.id,
                )
                .order_by(ServiceAddon.sort_order, ServiceAddon.name)
            )
        ).all()
    )
    await session.flush()
    _audit(session, context, "service_updated", "service", service.id)
    return _service_view(service, prices, [_addon_view(item) for item in addon_rows])


async def _replace_prices(
    session: AsyncSession,
    business_id: uuid.UUID,
    service: Service,
    requested: Sequence[VehiclePriceInput],
) -> list[VehiclePriceView]:
    await session.execute(delete(ServicePrice).where(ServicePrice.service_id == service.id))
    prices: list[VehiclePriceView] = []
    for item in requested:
        vehicle_type = str(item.vehicle_type)
        price_minor = item.price_minor
        session.add(
            ServicePrice(
                business_id=business_id,
                service_id=service.id,
                vehicle_type=vehicle_type,
                price_minor=price_minor,
            )
        )
        prices.append(VehiclePriceView(vehicle_type=vehicle_type, price_minor=price_minor))
    service.price_minor = min(item.price_minor for item in prices)
    return prices


async def create_addon(
    session: AsyncSession,
    context: StaffContext,
    service_id: uuid.UUID,
    request: AddonInput,
) -> AddonView:
    await _service_or_404(session, context.business_id, service_id)
    addon = ServiceAddon(
        business_id=context.business_id,
        service_id=service_id,
        name=request.name.strip(),
        description=request.description.strip() if request.description else None,
        price_minor=request.price_minor,
        default_duration_minutes=request.default_duration_minutes,
        mobile_available=request.mobile_available,
        shop_available=request.shop_available,
        is_active=request.is_active,
        sort_order=request.sort_order,
    )
    session.add(addon)
    await session.flush()
    _audit(session, context, "service_addon_created", "service_addon", addon.id)
    return _addon_view(addon)


async def update_addon(
    session: AsyncSession,
    context: StaffContext,
    addon_id: uuid.UUID,
    request: AddonPatch,
) -> AddonView:
    addon = await session.scalar(
        select(ServiceAddon)
        .where(ServiceAddon.id == addon_id, ServiceAddon.business_id == context.business_id)
        .with_for_update()
    )
    if addon is None:
        raise DomainError("SERVICE_ADDON_NOT_FOUND", "Add-on not found.", status_code=404)
    values = request.model_dump(exclude_unset=True)
    resulting_mobile = values.get("mobile_available", addon.mobile_available)
    resulting_shop = values.get("shop_available", addon.shop_available)
    if not resulting_mobile and not resulting_shop:
        raise DomainError("SERVICE_CHANNEL_REQUIRED", "Select Mobile, Shop, or both.")
    for key, value in values.items():
        if key in {"name", "description"} and isinstance(value, str):
            value = value.strip() or None
        setattr(addon, key, value)
    await session.flush()
    _audit(session, context, "service_addon_updated", "service_addon", addon.id)
    return _addon_view(addon)


async def get_business_booking_settings(
    session: AsyncSession, context: StaffContext
) -> BusinessBookingSettingsView:
    settings = await session.scalar(
        select(BusinessSettings).where(BusinessSettings.business_id == context.business_id)
    )
    if settings is None:
        raise DomainError(
            "BUSINESS_SETTINGS_NOT_FOUND",
            "Business settings are unavailable.",
            status_code=404,
        )
    hours = list(
        (
            await session.scalars(
                select(BusinessOperatingHour)
                .where(BusinessOperatingHour.business_id == context.business_id)
                .order_by(BusinessOperatingHour.weekday)
            )
        ).all()
    )
    return _settings_view(settings, hours)


async def update_business_booking_settings(
    session: AsyncSession,
    context: StaffContext,
    request: BusinessBookingSettingsPatch,
) -> BusinessBookingSettingsView:
    settings = await session.scalar(
        select(BusinessSettings)
        .where(BusinessSettings.business_id == context.business_id)
        .with_for_update()
    )
    if settings is None:
        raise DomainError(
            "BUSINESS_SETTINGS_NOT_FOUND",
            "Business settings are unavailable.",
            status_code=404,
        )
    values = request.model_dump(exclude_unset=True, exclude={"operating_hours"})
    if "loyalty_reward_service_id" in values and values["loyalty_reward_service_id"] is not None:
        service = await session.scalar(
            select(Service.id).where(
                Service.id == values["loyalty_reward_service_id"],
                Service.business_id == context.business_id,
                Service.is_active.is_(True),
            )
        )
        if service is None:
            raise DomainError(
                "LOYALTY_REWARD_SERVICE_NOT_FOUND",
                "Select an active reward service for this business.",
                status_code=404,
            )
    if (
        "default_inventory_location_id" in values
        and values["default_inventory_location_id"] is not None
    ):
        location = await session.scalar(
            select(InventoryLocation.id).where(
                InventoryLocation.id == values["default_inventory_location_id"],
                InventoryLocation.business_id == context.business_id,
                InventoryLocation.is_active.is_(True),
            )
        )
        if location is None:
            raise DomainError(
                "INVENTORY_LOCATION_NOT_FOUND",
                "Select an active stock location for this business.",
                status_code=404,
            )
    for key, value in values.items():
        setattr(settings, key, value)
    if request.operating_hours is not None:
        await session.execute(
            delete(BusinessOperatingHour).where(
                BusinessOperatingHour.business_id == context.business_id
            )
        )
        session.add_all(
            [
                BusinessOperatingHour(
                    business_id=context.business_id,
                    weekday=item.weekday,
                    is_open=item.is_open,
                    opening_time=item.opening_time if item.is_open else None,
                    closing_time=item.closing_time if item.is_open else None,
                )
                for item in request.operating_hours
            ]
        )
    await session.flush()
    _audit(session, context, "business_booking_settings_updated", "business_settings", settings.id)
    return await get_business_booking_settings(session, context)


def _service_view(
    service: Service, prices: list[VehiclePriceView], addons: list[AddonView]
) -> ServiceManagementView:
    return ServiceManagementView(
        id=service.id,
        name=service.name,
        description=service.description,
        default_duration_minutes=service.estimated_duration_minutes,
        mobile_available=service.mobile_available,
        shop_available=service.shop_available,
        is_active=service.is_active,
        sort_order=service.sort_order,
        prices=prices,
        addons=addons,
    )


def _addon_view(addon: ServiceAddon) -> AddonView:
    return AddonView(
        id=addon.id,
        service_id=addon.service_id,
        name=addon.name,
        description=addon.description,
        price_minor=addon.price_minor,
        default_duration_minutes=addon.default_duration_minutes,
        mobile_available=addon.mobile_available,
        shop_available=addon.shop_available,
        is_active=addon.is_active,
        sort_order=addon.sort_order,
    )


def _settings_view(
    settings: BusinessSettings, hours: list[BusinessOperatingHour]
) -> BusinessBookingSettingsView:
    return BusinessBookingSettingsView(
        currency_code=settings.currency_code,
        slot_duration_minutes=settings.slot_duration_minutes,
        cancellation_cutoff_hours=settings.cancellation_cutoff_hours,
        mobile_minimum_enabled=settings.mobile_minimum_enabled,
        mobile_minimum_minor=settings.mobile_minimum_minor,
        default_team_turnaround_minutes=settings.default_team_turnaround_minutes,
        default_inventory_location_id=settings.default_inventory_location_id,
        loyalty_reward_service_id=settings.loyalty_reward_service_id,
        operating_hours=[
            OperatingHourView(
                weekday=item.weekday,
                is_open=item.is_open,
                opening_time=item.opening_time,
                closing_time=item.closing_time,
            )
            for item in hours
        ],
    )

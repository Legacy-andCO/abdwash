import uuid
from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import StaffContext
from app.domain.errors import ConflictError, DomainError
from app.models.entities import (
    AuditEvent,
    Coupon,
    CouponServiceEligibility,
    CouponVehicleEligibility,
    Service,
    ServicePrice,
)
from app.repositories.business import load_default_business
from app.schemas.coupons import (
    CouponCheckoutLine,
    CouponEligibleLine,
    CouponList,
    CouponServiceView,
    CouponValidationRequest,
    CouponValidationResponse,
    CouponView,
    CouponWrite,
)


def percentage_discount(price_minor: int, discount_percent: int) -> int:
    """Round a percentage discount to the nearest minor currency unit."""
    return min(price_minor, (price_minor * discount_percent + 50) // 100)


async def validate_public_coupon(
    session: AsyncSession, request: CouponValidationRequest
) -> CouponValidationResponse:
    configuration = await load_default_business(session)
    return await resolve_coupon(
        session,
        business_id=configuration.business.id,
        currency_code=configuration.settings.currency_code,
        code=request.code,
        lines=request.lines,
        selected_line_position=request.selected_line_position,
    )


async def resolve_coupon(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    currency_code: str,
    code: str,
    lines: Sequence[CouponCheckoutLine],
    selected_line_position: int | None,
    lock: bool = False,
) -> CouponValidationResponse:
    statement = select(Coupon).where(
        Coupon.business_id == business_id,
        Coupon.code == code,
        Coupon.is_active.is_(True),
    )
    if lock:
        statement = statement.with_for_update()
    coupon = await session.scalar(statement)
    if coupon is None:
        raise DomainError("COUPON_INVALID", "This coupon code is not valid.", status_code=422)
    if coupon.minimum_vehicle_count is not None and len(lines) < coupon.minimum_vehicle_count:
        raise DomainError(
            "COUPON_MINIMUM_VEHICLES",
            f"This coupon requires at least {coupon.minimum_vehicle_count} vehicles.",
            status_code=422,
            details={"minimum_vehicle_count": coupon.minimum_vehicle_count},
        )

    service_ids = set(
        (
            await session.scalars(
                select(CouponServiceEligibility.service_id).where(
                    CouponServiceEligibility.coupon_id == coupon.id
                )
            )
        ).all()
    )
    vehicle_types = set(
        (
            await session.scalars(
                select(CouponVehicleEligibility.vehicle_type).where(
                    CouponVehicleEligibility.coupon_id == coupon.id
                )
            )
        ).all()
    )
    requested_service_ids = {line.service_id for line in lines}
    service_rows = list(
        (
            await session.scalars(
                select(Service).where(
                    Service.business_id == business_id,
                    Service.id.in_(requested_service_ids),
                    Service.is_active.is_(True),
                )
            )
        ).all()
    )
    services = {service.id: service for service in service_rows}
    price_rows = list(
        (
            await session.scalars(
                select(ServicePrice).where(
                    ServicePrice.business_id == business_id,
                    ServicePrice.service_id.in_(requested_service_ids),
                )
            )
        ).all()
    )
    prices = {(row.service_id, row.vehicle_type): row.price_minor for row in price_rows}

    service_matches = [line for line in lines if line.service_id in service_ids]
    if not service_matches:
        raise DomainError(
            "COUPON_SERVICE_INELIGIBLE",
            "This coupon does not apply to the selected service.",
            status_code=422,
        )
    vehicle_matches = [line for line in service_matches if line.vehicle_type in vehicle_types]
    if not vehicle_matches:
        raise DomainError(
            "COUPON_VEHICLE_INELIGIBLE",
            "This coupon is not valid for this vehicle type.",
            status_code=422,
        )
    eligible_source = [
        line
        for line in vehicle_matches
        if line.loyalty_reward_id is None
        and line.service_id in services
        and (line.service_id, line.vehicle_type) in prices
    ]
    if not eligible_source:
        if any(line.loyalty_reward_id is not None for line in vehicle_matches):
            raise DomainError(
                "COUPON_LOYALTY_CONFLICT",
                "A coupon cannot be combined with a loyalty reward on the same service.",
                status_code=422,
            )
        raise DomainError(
            "COUPON_LINE_INELIGIBLE",
            "This coupon cannot be applied to the selected booking item.",
            status_code=422,
        )

    eligible_lines = [
        CouponEligibleLine(
            position=line.position,
            service_id=line.service_id,
            service_name=services[line.service_id].name,
            vehicle_type=line.vehicle_type,
            make=line.make,
            model=line.model,
            list_price_minor=prices[(line.service_id, line.vehicle_type)],
            discount_minor=percentage_discount(
                prices[(line.service_id, line.vehicle_type)], coupon.discount_percent
            ),
        )
        for line in eligible_source
    ]
    chosen_position = selected_line_position
    if chosen_position is None and len(eligible_lines) == 1:
        chosen_position = eligible_lines[0].position
    chosen = next(
        (line for line in eligible_lines if line.position == chosen_position),
        None,
    )
    if selected_line_position is not None and chosen is None:
        selected = next(line for line in lines if line.position == selected_line_position)
        if selected.loyalty_reward_id is not None:
            raise DomainError(
                "COUPON_LOYALTY_CONFLICT",
                "A coupon cannot be combined with a loyalty reward on the same service.",
                status_code=422,
            )
        raise DomainError(
            "COUPON_LINE_INELIGIBLE",
            "This coupon cannot be applied to the selected booking item.",
            status_code=422,
        )
    return CouponValidationResponse(
        coupon_id=coupon.id,
        code=coupon.code,
        discount_percent=coupon.discount_percent,
        minimum_vehicle_count=coupon.minimum_vehicle_count,
        currency_code=currency_code,
        eligible_lines=eligible_lines,
        selected_line_position=chosen_position,
        discount_minor=chosen.discount_minor if chosen else 0,
    )


async def list_coupons(session: AsyncSession, context: StaffContext) -> CouponList:
    coupons = list(
        (
            await session.scalars(
                select(Coupon)
                .where(Coupon.business_id == context.business_id)
                .order_by(Coupon.created_at.desc(), Coupon.code)
            )
        ).all()
    )
    return CouponList(coupons=await _coupon_views(session, coupons))


async def create_coupon(
    session: AsyncSession, context: StaffContext, request: CouponWrite
) -> CouponView:
    await _validate_services(session, context.business_id, request.service_ids)
    coupon = Coupon(
        business_id=context.business_id,
        code=request.code,
        discount_percent=request.discount_percent,
        minimum_vehicle_count=request.minimum_vehicle_count,
        is_active=request.is_active,
        created_by_staff_id=context.staff_id,
    )
    session.add(coupon)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "COUPON_CODE_EXISTS", "A coupon with this code already exists."
        ) from exc
    await _replace_eligibility(session, coupon.id, request)
    _audit(session, context, "coupon_created", coupon.id)
    await session.flush()
    return (await _coupon_views(session, [coupon]))[0]


async def update_coupon(
    session: AsyncSession,
    context: StaffContext,
    coupon_id: uuid.UUID,
    request: CouponWrite,
) -> CouponView:
    coupon = await session.scalar(
        select(Coupon)
        .where(Coupon.id == coupon_id, Coupon.business_id == context.business_id)
        .with_for_update()
    )
    if coupon is None:
        raise DomainError("COUPON_NOT_FOUND", "Coupon not found.", status_code=404)
    await _validate_services(session, context.business_id, request.service_ids)
    coupon.code = request.code
    coupon.discount_percent = request.discount_percent
    coupon.minimum_vehicle_count = request.minimum_vehicle_count
    coupon.is_active = request.is_active
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "COUPON_CODE_EXISTS", "A coupon with this code already exists."
        ) from exc
    await _replace_eligibility(session, coupon.id, request)
    _audit(session, context, "coupon_updated", coupon.id)
    await session.flush()
    return (await _coupon_views(session, [coupon]))[0]


async def _validate_services(
    session: AsyncSession, business_id: uuid.UUID, service_ids: Sequence[uuid.UUID]
) -> None:
    found = set(
        (
            await session.scalars(
                select(Service.id).where(
                    Service.id.in_(service_ids),
                    Service.business_id == business_id,
                    Service.is_active.is_(True),
                )
            )
        ).all()
    )
    if found != set(service_ids):
        raise DomainError(
            "COUPON_SERVICE_INVALID",
            "Choose only active services from this business.",
            status_code=422,
        )


async def _replace_eligibility(
    session: AsyncSession, coupon_id: uuid.UUID, request: CouponWrite
) -> None:
    await session.execute(
        delete(CouponServiceEligibility).where(CouponServiceEligibility.coupon_id == coupon_id)
    )
    await session.execute(
        delete(CouponVehicleEligibility).where(CouponVehicleEligibility.coupon_id == coupon_id)
    )
    session.add_all(
        [
            CouponServiceEligibility(coupon_id=coupon_id, service_id=service_id)
            for service_id in request.service_ids
        ]
        + [
            CouponVehicleEligibility(coupon_id=coupon_id, vehicle_type=str(vehicle_type))
            for vehicle_type in request.vehicle_types
        ]
    )


async def _coupon_views(session: AsyncSession, coupons: Sequence[Coupon]) -> list[CouponView]:
    if not coupons:
        return []
    coupon_ids = [coupon.id for coupon in coupons]
    service_rows = (
        await session.execute(
            select(CouponServiceEligibility.coupon_id, Service.id, Service.name)
            .join(Service, Service.id == CouponServiceEligibility.service_id)
            .where(CouponServiceEligibility.coupon_id.in_(coupon_ids))
            .order_by(Service.sort_order, Service.name)
        )
    ).all()
    vehicle_rows = (
        await session.execute(
            select(CouponVehicleEligibility.coupon_id, CouponVehicleEligibility.vehicle_type)
            .where(CouponVehicleEligibility.coupon_id.in_(coupon_ids))
            .order_by(CouponVehicleEligibility.vehicle_type)
        )
    ).all()
    services: dict[uuid.UUID, list[CouponServiceView]] = defaultdict(list)
    vehicles: dict[uuid.UUID, list[str]] = defaultdict(list)
    for coupon_id, service_id, service_name in service_rows:
        services[coupon_id].append(CouponServiceView(id=service_id, name=service_name))
    for coupon_id, vehicle_type in vehicle_rows:
        vehicles[coupon_id].append(vehicle_type)
    return [
        CouponView(
            id=coupon.id,
            code=coupon.code,
            discount_percent=coupon.discount_percent,
            minimum_vehicle_count=coupon.minimum_vehicle_count,
            is_active=coupon.is_active,
            services=services[coupon.id],
            vehicle_types=vehicles[coupon.id],
            created_at=coupon.created_at,
            updated_at=coupon.updated_at,
        )
        for coupon in coupons
    ]


def _audit(
    session: AsyncSession, context: StaffContext, event_type: str, coupon_id: uuid.UUID
) -> None:
    session.add(
        AuditEvent(
            business_id=context.business_id,
            actor_auth_user_id=context.auth_user_id,
            event_type=event_type,
            entity_type="coupon",
            entity_id=coupon_id,
            metadata_json={},
        )
    )

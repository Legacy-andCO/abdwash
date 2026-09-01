import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import LoyaltyEventType, LoyaltyRewardStatus, PaymentStatus
from app.domain.errors import ConflictError, DomainError
from app.models.entities import (
    Booking,
    BookingService,
    BookingVehicle,
    BusinessSettings,
    CustomerProfile,
    Job,
    LoyaltyEvent,
    LoyaltyReward,
    Payment,
    Service,
)
from app.schemas.loyalty import (
    LoyaltyAdjustment,
    LoyaltyHistoryItem,
    LoyaltyRewardService,
    LoyaltyRewardView,
    LoyaltySettingsUpdate,
    LoyaltySettingsView,
    LoyaltySummary,
)


def _reward_service(service_id: uuid.UUID, name: str) -> LoyaltyRewardService:
    return LoyaltyRewardService(id=service_id, name=name)


def loyalty_progress_from_ledger(credit_total: int, reward_requirements: list[int]) -> int:
    return max(0, credit_total - sum(reward_requirements))


def is_qualifying_service_line(
    *,
    payment_status: str,
    booking_source: str,
    line_total_minor: int,
    loyalty_reward_id: uuid.UUID | None,
    discount_type: str | None,
) -> bool:
    return (
        payment_status == PaymentStatus.PAID
        and booking_source != "rewash"
        and line_total_minor > 0
        and loyalty_reward_id is None
        and discount_type is None
    )


async def _settings_and_service(
    session: AsyncSession, business_id: uuid.UUID, *, lock: bool = False
) -> tuple[BusinessSettings, Service | None]:
    statement = (
        select(BusinessSettings, Service)
        .select_from(BusinessSettings)
        .outerjoin(
            Service,
            (Service.id == BusinessSettings.loyalty_reward_service_id)
            & (Service.business_id == BusinessSettings.business_id),
        )
        .where(BusinessSettings.business_id == business_id)
    )
    if lock:
        statement = statement.with_for_update(of=BusinessSettings)
    row = (await session.execute(statement)).one()
    return row[0], row[1]


async def loyalty_summary(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    customer_profile_id: uuid.UUID,
    history_limit: int = 20,
) -> LoyaltySummary:
    settings, service = await _settings_and_service(session, business_id)
    credit_total, qualifying_total = (
        await session.execute(
            select(
                func.coalesce(
                    func.sum(LoyaltyEvent.quantity).filter(
                        LoyaltyEvent.event_type.in_(
                            [
                                LoyaltyEventType.QUALIFYING_WASH,
                                LoyaltyEventType.FIRST_REVIEW_BONUS,
                                LoyaltyEventType.MANUAL_CREDIT,
                                LoyaltyEventType.MANUAL_DEBIT,
                            ]
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(LoyaltyEvent.quantity).filter(
                        LoyaltyEvent.event_type == LoyaltyEventType.QUALIFYING_WASH
                    ),
                    0,
                ),
            ).where(
                LoyaltyEvent.business_id == business_id,
                LoyaltyEvent.customer_profile_id == customer_profile_id,
            )
        )
    ).one()
    credit_total = int(credit_total or 0)
    qualifying_total = int(qualifying_total or 0)
    rewards = list(
        (
            await session.scalars(
                select(LoyaltyReward)
                .where(
                    LoyaltyReward.business_id == business_id,
                    LoyaltyReward.customer_profile_id == customer_profile_id,
                )
                .order_by(LoyaltyReward.created_at.desc())
            )
        ).all()
    )
    progress = loyalty_progress_from_ledger(
        credit_total, [reward.required_washes for reward in rewards]
    )
    history_rows = (
        await session.execute(
            select(
                LoyaltyEvent,
                Booking.reference,
                BookingVehicle.make,
                BookingVehicle.model,
                BookingVehicle.plate_number,
            )
            .select_from(LoyaltyEvent)
            .outerjoin(Booking, Booking.id == LoyaltyEvent.booking_id)
            .outerjoin(BookingVehicle, BookingVehicle.id == LoyaltyEvent.booking_vehicle_id)
            .where(
                LoyaltyEvent.business_id == business_id,
                LoyaltyEvent.customer_profile_id == customer_profile_id,
            )
            .order_by(LoyaltyEvent.created_at.desc())
            .limit(history_limit)
        )
    ).all()
    required = settings.loyalty_required_washes
    return LoyaltySummary(
        enabled=settings.loyalty_enabled,
        configured=service is not None,
        required_washes=required,
        progress_washes=progress,
        washes_remaining=max(0, required - progress),
        lifetime_qualifying_washes=max(0, qualifying_total),
        available_rewards=sum(reward.status == LoyaltyRewardStatus.AVAILABLE for reward in rewards),
        reserved_rewards=sum(reward.status == LoyaltyRewardStatus.RESERVED for reward in rewards),
        redeemed_rewards=sum(reward.status == LoyaltyRewardStatus.REDEEMED for reward in rewards),
        reward_service=_reward_service(service.id, service.name) if service else None,
        rewards=[
            LoyaltyRewardView(
                id=reward.id,
                service=_reward_service(reward.reward_service_id, reward.reward_service_name),
                list_price_minor=reward.reward_list_price_minor,
                status=reward.status,
                created_at=reward.created_at,
                reserved_at=reward.reserved_at,
                redeemed_at=reward.redeemed_at,
            )
            for reward in rewards
        ],
        history=[
            LoyaltyHistoryItem(
                id=event.id,
                event_type=event.event_type,
                quantity=event.quantity,
                reason=event.reason,
                booking_reference=reference,
                vehicle_label=(" ".join(part for part in (make, model, plate) if part) or None),
                created_at=event.created_at,
            )
            for event, reference, make, model, plate in history_rows
        ],
    )


async def _earn_available_rewards(
    session: AsyncSession, *, business_id: uuid.UUID, customer_profile_id: uuid.UUID
) -> None:
    profile = await session.scalar(
        select(CustomerProfile)
        .where(
            CustomerProfile.id == customer_profile_id,
            CustomerProfile.business_id == business_id,
        )
        .with_for_update()
    )
    if profile is None:
        return
    settings, service = await _settings_and_service(session, business_id, lock=True)
    if not settings.loyalty_enabled or service is None or not service.is_active:
        return
    credit_total = int(
        await session.scalar(
            select(func.coalesce(func.sum(LoyaltyEvent.quantity), 0)).where(
                LoyaltyEvent.business_id == business_id,
                LoyaltyEvent.customer_profile_id == customer_profile_id,
                LoyaltyEvent.event_type.in_(
                    [
                        LoyaltyEventType.QUALIFYING_WASH,
                        LoyaltyEventType.FIRST_REVIEW_BONUS,
                        LoyaltyEventType.MANUAL_CREDIT,
                        LoyaltyEventType.MANUAL_DEBIT,
                    ]
                ),
            )
        )
        or 0
    )
    consumed = int(
        await session.scalar(
            select(func.coalesce(func.sum(LoyaltyReward.required_washes), 0)).where(
                LoyaltyReward.business_id == business_id,
                LoyaltyReward.customer_profile_id == customer_profile_id,
            )
        )
        or 0
    )
    earn_count = max(0, credit_total - consumed) // settings.loyalty_required_washes
    for _ in range(earn_count):
        reward = LoyaltyReward(
            business_id=business_id,
            customer_profile_id=customer_profile_id,
            reward_service_id=service.id,
            reward_service_name=service.name,
            reward_list_price_minor=service.price_minor,
            required_washes=settings.loyalty_required_washes,
            status=LoyaltyRewardStatus.AVAILABLE,
        )
        session.add(reward)
        await session.flush()
        session.add(
            LoyaltyEvent(
                business_id=business_id,
                customer_profile_id=customer_profile_id,
                event_type=LoyaltyEventType.REWARD_EARNED,
                quantity=0,
                reward_id=reward.id,
                source_key=f"reward-earned:{reward.id}",
            )
        )


async def evaluate_loyalty_for_job(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
    row = (
        await session.execute(
            select(Job, Booking, Payment)
            .select_from(Job)
            .join(Booking, Booking.id == Job.booking_id)
            .join(Payment, Payment.booking_id == Booking.id)
            .where(Job.id == job_id, Booking.business_id == business_id)
        )
    ).one_or_none()
    if row is None:
        return
    job, booking, payment = row
    if job.status != "completed" or booking.customer_profile_id is None:
        return
    lines = list(
        (
            await session.scalars(
                select(BookingService).where(BookingService.booking_id == booking.id)
            )
        ).all()
    )
    now = datetime.now(UTC)
    for line in lines:
        if line.loyalty_reward_id is not None:
            reward = await session.scalar(
                select(LoyaltyReward)
                .where(
                    LoyaltyReward.id == line.loyalty_reward_id,
                    LoyaltyReward.business_id == business_id,
                    LoyaltyReward.customer_profile_id == booking.customer_profile_id,
                )
                .with_for_update()
            )
            if reward is not None and reward.status == LoyaltyRewardStatus.RESERVED:
                reward.status = LoyaltyRewardStatus.REDEEMED
                reward.redeemed_job_id = job.id
                reward.redeemed_at = now
                session.add(
                    LoyaltyEvent(
                        business_id=business_id,
                        customer_profile_id=booking.customer_profile_id,
                        event_type=LoyaltyEventType.REWARD_REDEEMED,
                        quantity=0,
                        job_id=job.id,
                        booking_id=booking.id,
                        booking_vehicle_id=line.booking_vehicle_id,
                        reward_id=reward.id,
                        source_key=f"reward-redeemed:{reward.id}",
                    )
                )
    if payment.status != PaymentStatus.PAID or booking.source == "rewash":
        return
    for line in lines:
        source_key = f"qualifying:{line.id}"
        exists = await session.scalar(
            select(LoyaltyEvent.id).where(
                LoyaltyEvent.business_id == business_id,
                LoyaltyEvent.source_key == source_key,
            )
        )
        if exists is None and is_qualifying_service_line(
            payment_status=payment.status,
            booking_source=booking.source,
            line_total_minor=line.line_total_minor,
            loyalty_reward_id=line.loyalty_reward_id,
            discount_type=line.discount_type,
        ):
            session.add(
                LoyaltyEvent(
                    business_id=business_id,
                    customer_profile_id=booking.customer_profile_id,
                    event_type=LoyaltyEventType.QUALIFYING_WASH,
                    quantity=1,
                    job_id=job.id,
                    booking_id=booking.id,
                    booking_vehicle_id=line.booking_vehicle_id,
                    source_key=source_key,
                )
            )
    await session.flush()
    await _earn_available_rewards(
        session, business_id=business_id, customer_profile_id=booking.customer_profile_id
    )


async def first_review_bonus_available(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    customer_profile_id: uuid.UUID,
) -> bool:
    awarded = await session.scalar(
        select(LoyaltyEvent.id).where(
            LoyaltyEvent.business_id == business_id,
            LoyaltyEvent.customer_profile_id == customer_profile_id,
            LoyaltyEvent.event_type == LoyaltyEventType.FIRST_REVIEW_BONUS,
        )
    )
    return awarded is None


async def award_first_review_bonus(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    customer_profile_id: uuid.UUID,
    booking_id: uuid.UUID,
) -> bool:
    if not await first_review_bonus_available(
        session,
        business_id=business_id,
        customer_profile_id=customer_profile_id,
    ):
        return False
    session.add(
        LoyaltyEvent(
            business_id=business_id,
            customer_profile_id=customer_profile_id,
            event_type=LoyaltyEventType.FIRST_REVIEW_BONUS,
            quantity=1,
            booking_id=booking_id,
            reason="First authenticated customer review bonus",
            source_key=f"first-review-bonus:{customer_profile_id}",
        )
    )
    await session.flush()
    await _earn_available_rewards(
        session,
        business_id=business_id,
        customer_profile_id=customer_profile_id,
    )
    return True


async def release_booking_rewards(
    session: AsyncSession, *, business_id: uuid.UUID, booking: Booking
) -> None:
    if booking.customer_profile_id is None:
        return
    rewards = list(
        (
            await session.scalars(
                select(LoyaltyReward)
                .where(
                    LoyaltyReward.business_id == business_id,
                    LoyaltyReward.customer_profile_id == booking.customer_profile_id,
                    LoyaltyReward.reserved_booking_id == booking.id,
                    LoyaltyReward.status == LoyaltyRewardStatus.RESERVED,
                )
                .with_for_update()
            )
        ).all()
    )
    for reward in rewards:
        reward.status = LoyaltyRewardStatus.AVAILABLE
        reward.reserved_booking_id = None
        reward.reserved_booking_service_id = None
        reward.reserved_at = None
        session.add(
            LoyaltyEvent(
                business_id=business_id,
                customer_profile_id=booking.customer_profile_id,
                event_type=LoyaltyEventType.REWARD_RELEASED,
                quantity=0,
                booking_id=booking.id,
                reward_id=reward.id,
                source_key=f"reward-released:{reward.id}:{booking.id}",
            )
        )


async def get_loyalty_settings(
    session: AsyncSession, business_id: uuid.UUID
) -> LoyaltySettingsView:
    settings, service = await _settings_and_service(session, business_id)
    return LoyaltySettingsView(
        enabled=settings.loyalty_enabled,
        required_washes=settings.loyalty_required_washes,
        reward_service=_reward_service(service.id, service.name) if service else None,
    )


async def update_loyalty_settings(
    session: AsyncSession, business_id: uuid.UUID, request: LoyaltySettingsUpdate
) -> LoyaltySettingsView:
    settings, _service = await _settings_and_service(session, business_id, lock=True)
    service = None
    if request.reward_service_id is not None:
        service = await session.scalar(
            select(Service).where(
                Service.id == request.reward_service_id,
                Service.business_id == business_id,
                Service.is_active.is_(True),
            )
        )
        if service is None:
            raise DomainError(
                "LOYALTY_REWARD_SERVICE_NOT_FOUND",
                "Select an active reward service for this business.",
                status_code=404,
            )
    if request.enabled and service is None:
        raise DomainError(
            "LOYALTY_REWARD_SERVICE_REQUIRED",
            "A reward service is required before loyalty can be enabled.",
            status_code=409,
        )
    settings.loyalty_enabled = request.enabled
    settings.loyalty_required_washes = request.required_washes
    settings.loyalty_reward_service_id = service.id if service else None
    await session.flush()
    return LoyaltySettingsView(
        enabled=settings.loyalty_enabled,
        required_washes=settings.loyalty_required_washes,
        reward_service=_reward_service(service.id, service.name) if service else None,
    )


async def adjust_loyalty(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    customer_profile_id: uuid.UUID,
    actor_staff_id: uuid.UUID,
    request: LoyaltyAdjustment,
) -> LoyaltySummary:
    profile = await session.scalar(
        select(CustomerProfile)
        .where(
            CustomerProfile.id == customer_profile_id,
            CustomerProfile.business_id == business_id,
            CustomerProfile.is_active.is_(True),
        )
        .with_for_update()
    )
    if profile is None:
        raise DomainError("CUSTOMER_NOT_FOUND", "Customer not found.", status_code=404)
    source_key = f"manual:{request.client_event_id}"
    if (
        await session.scalar(
            select(LoyaltyEvent.id).where(
                LoyaltyEvent.business_id == business_id, LoyaltyEvent.source_key == source_key
            )
        )
        is None
    ):
        current = await loyalty_summary(
            session, business_id=business_id, customer_profile_id=customer_profile_id
        )
        quantity = request.washes if request.direction == "credit" else -request.washes
        if quantity < 0 and request.washes > current.progress_washes:
            raise ConflictError(
                "LOYALTY_DEBIT_EXCEEDS_PROGRESS",
                "The adjustment exceeds the customer's unconverted wash progress.",
            )
        session.add(
            LoyaltyEvent(
                business_id=business_id,
                customer_profile_id=customer_profile_id,
                event_type=(
                    LoyaltyEventType.MANUAL_CREDIT
                    if quantity > 0
                    else LoyaltyEventType.MANUAL_DEBIT
                ),
                quantity=quantity,
                actor_staff_id=actor_staff_id,
                reason=request.reason,
                source_key=source_key,
            )
        )
        await session.flush()
        await _earn_available_rewards(
            session, business_id=business_id, customer_profile_id=customer_profile_id
        )
    return await loyalty_summary(
        session, business_id=business_id, customer_profile_id=customer_profile_id
    )

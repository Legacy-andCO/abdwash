import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DomainError
from app.models.entities import Business, BusinessSettings, Service

DEFAULT_BUSINESS_SLUG = "abdwash"


@dataclass(frozen=True)
class BusinessConfiguration:
    business: Business
    settings: BusinessSettings


async def load_default_business(session: AsyncSession) -> BusinessConfiguration:
    row = (
        await session.execute(
            select(Business, BusinessSettings)
            .join(BusinessSettings, BusinessSettings.business_id == Business.id)
            .where(Business.slug == DEFAULT_BUSINESS_SLUG, Business.is_active.is_(True))
        )
    ).one_or_none()
    if row is None:
        raise RuntimeError("Trifecta bootstrap data is missing; run the explicit seed command.")
    return BusinessConfiguration(business=row[0], settings=row[1])


async def load_active_services(session: AsyncSession, business_id: object) -> list[Service]:
    return list(
        (
            await session.scalars(
                select(Service)
                .where(Service.business_id == business_id, Service.is_active.is_(True))
                .order_by(Service.sort_order, Service.name)
            )
        ).all()
    )


async def load_staff_business(
    session: AsyncSession, business_id: uuid.UUID
) -> BusinessConfiguration:
    row = (
        await session.execute(
            select(Business, BusinessSettings)
            .join(BusinessSettings, BusinessSettings.business_id == Business.id)
            .where(Business.id == business_id, Business.is_active.is_(True))
        )
    ).one_or_none()
    if row is None:
        raise DomainError(
            "BUSINESS_UNAVAILABLE", "Business scheduling is unavailable.", status_code=403
        )
    return BusinessConfiguration(business=row[0], settings=row[1])

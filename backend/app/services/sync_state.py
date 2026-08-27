import uuid
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import BusinessSyncRevision
from app.schemas.staff import SyncState

SyncDomain = Literal["jobs", "workforce", "schedule", "finance", "customers"]

_COLUMNS = {
    "jobs": BusinessSyncRevision.jobs_revision,
    "workforce": BusinessSyncRevision.workforce_revision,
    "schedule": BusinessSyncRevision.schedule_revision,
    "finance": BusinessSyncRevision.finance_revision,
    "customers": BusinessSyncRevision.customers_revision,
}


async def bump_sync_revisions(
    session: AsyncSession,
    business_id: uuid.UUID,
    *domains: SyncDomain,
) -> None:
    selected = set(domains)
    if not selected:
        return
    initial = {f"{domain}_revision": int(domain in selected) for domain in _COLUMNS}
    updates: dict[str, Any] = {
        f"{domain}_revision": column + 1
        for domain, column in _COLUMNS.items()
        if domain in selected
    }
    updates["updated_at"] = func.now()
    statement = (
        insert(BusinessSyncRevision)
        .values(business_id=business_id, **initial)
        .on_conflict_do_update(
            index_elements=[BusinessSyncRevision.business_id],
            set_=updates,
        )
    )
    await session.execute(statement)


async def get_sync_state(session: AsyncSession, business_id: uuid.UUID) -> SyncState:
    row = await session.scalar(
        select(BusinessSyncRevision).where(BusinessSyncRevision.business_id == business_id)
    )
    if row is None:
        return SyncState(jobs=0, workforce=0, schedule=0, finance=0, customers=0)
    return SyncState(
        jobs=row.jobs_revision,
        workforce=row.workforce_revision,
        schedule=row.schedule_revision,
        finance=row.finance_revision,
        customers=row.customers_revision or 0,
    )

import time
import uuid
from dataclasses import dataclass
from typing import Annotated, Any, cast

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.verifier import AuthenticationError, VerifiedIdentity
from app.core.database import session_dependency
from app.domain.enums import StaffRole
from app.models.entities import Business, BusinessSettings, StaffProfile

bearer = HTTPBearer(auto_error=False)
SessionDep = Annotated[AsyncSession, Depends(session_dependency)]


@dataclass(frozen=True)
class StaffContext:
    auth_user_id: uuid.UUID
    staff_id: uuid.UUID
    business_id: uuid.UUID
    business_name: str
    role: StaffRole
    timezone: str
    display_name: str = ""
    username: str = ""
    phone: str | None = None


async def optional_identity(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> VerifiedIdentity | None:
    if credentials is None:
        return None
    started = time.perf_counter()
    try:
        verifier = cast(Any, request.app.state.auth_verifier)
        return cast(VerifiedIdentity, await verifier.verify(credentials.credentials))
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN"}) from exc
    finally:
        request.state.auth_ms = (time.perf_counter() - started) * 1000


async def required_identity(
    identity: Annotated[VerifiedIdentity | None, Depends(optional_identity)],
) -> VerifiedIdentity:
    if identity is None:
        raise HTTPException(status_code=401, detail={"code": "AUTHENTICATION_REQUIRED"})
    return identity


async def staff_context(
    request: Request,
    identity: Annotated[VerifiedIdentity, Depends(required_identity)],
    session: SessionDep,
) -> StaffContext:
    started = time.perf_counter()
    statement = (
        select(StaffProfile, Business.name, BusinessSettings.timezone)
        .join(Business, Business.id == StaffProfile.business_id)
        .join(BusinessSettings, BusinessSettings.business_id == Business.id)
        .where(StaffProfile.auth_user_id == identity.user_id, StaffProfile.is_active.is_(True))
    )
    # SQLAlchemy SELECTs autobegin a transaction. Resolve the immutable request
    # context inside an explicit read boundary so staff mutation routes receive
    # the shared request session with no transaction still active.
    try:
        async with session.begin():
            row = (await session.execute(statement)).one_or_none()
            if row is None:
                raise HTTPException(status_code=403, detail={"code": "STAFF_ACCESS_REQUIRED"})
            staff, business_name, timezone = row
            context = StaffContext(
                auth_user_id=identity.user_id,
                staff_id=staff.id,
                business_id=staff.business_id,
                business_name=business_name,
                role=StaffRole(staff.role),
                timezone=timezone,
                display_name=staff.display_name,
                username=staff.username,
                phone=staff.phone,
            )
        return context
    finally:
        request.state.staff_context_ms = (time.perf_counter() - started) * 1000


def require_roles(*roles: StaffRole) -> Any:
    async def dependency(
        context: Annotated[StaffContext, Depends(staff_context)],
    ) -> StaffContext:
        if context.role not in roles:
            raise HTTPException(status_code=403, detail={"code": "INSUFFICIENT_ROLE"})
        return context

    return dependency


ManagerContext = Annotated[StaffContext, Depends(require_roles(StaffRole.MANAGER, StaffRole.ADMIN))]
AdminContext = Annotated[StaffContext, Depends(require_roles(StaffRole.ADMIN))]

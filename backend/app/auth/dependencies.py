import time
import uuid
from dataclasses import dataclass
from typing import Annotated, Any, cast

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.mfa import require_privileged_totp
from app.auth.sessions import require_active_session
from app.auth.verifier import (
    AuthenticationError,
    AuthenticationServiceUnavailable,
    VerifiedIdentity,
)
from app.core.config import get_settings
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
    must_change_password: bool = False


async def optional_identity(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> VerifiedIdentity | None:
    if credentials is None:
        return None
    started = time.perf_counter()
    try:
        verifier = cast(Any, request.app.state.auth_verifier)
        identity = cast(VerifiedIdentity, await verifier.verify(credentials.credentials))
        if get_settings().is_deployed:
            async with request.app.state.session_factory() as auth_session, auth_session.begin():
                await require_active_session(auth_session, identity)
        return identity
    except AuthenticationServiceUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "AUTHENTICATION_SERVICE_UNAVAILABLE"},
        ) from exc
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


# These existing operational writes still require verified AAL2 for privileged roles.
# All other writes retain the five-minute step-up, including finance and access changes.
ROUTINE_STAFF_WRITES = {
    ("POST", "/api/v1/staff/attendance/clock-in"),
    ("POST", "/api/v1/staff/attendance/clock-out"),
    ("POST", "/api/v1/staff/jobs/{job_id}/start-trip"),
    ("POST", "/api/v1/staff/jobs/{job_id}/arrive"),
    ("POST", "/api/v1/staff/jobs/{job_id}/start"),
    ("POST", "/api/v1/staff/jobs/{job_id}/complete"),
    ("PUT", "/api/v1/staff/jobs/{job_id}/quality/checklist"),
    ("PUT", "/api/v1/staff/jobs/{job_id}/quality/inspection"),
    ("POST", "/api/v1/staff/jobs/{job_id}/quality/issues"),
    ("POST", "/api/v1/staff/jobs/{job_id}/quality/photos/upload"),
    ("POST", "/api/v1/staff/jobs/{job_id}/quality/photos/{photo_id}/complete"),
}


async def staff_context(
    request: Request,
    identity: Annotated[VerifiedIdentity, Depends(required_identity)],
    session: SessionDep,
) -> StaffContext:
    started = time.perf_counter()
    statement = (
        select(
            StaffProfile.id.label("staff_id"),
            StaffProfile.business_id,
            StaffProfile.role,
            StaffProfile.display_name,
            StaffProfile.username,
            StaffProfile.phone,
            StaffProfile.must_change_password,
            Business.name.label("business_name"),
            BusinessSettings.timezone,
        )
        .join(Business, Business.id == StaffProfile.business_id)
        .join(BusinessSettings, BusinessSettings.business_id == Business.id)
        .where(
            StaffProfile.auth_user_id == identity.user_id,
            StaffProfile.is_active.is_(True),
            Business.is_active.is_(True),
        )
    )
    # SQLAlchemy SELECTs autobegin a transaction. Resolve the immutable request
    # context inside an explicit read boundary so staff mutation routes receive
    # the shared request session with no transaction still active.
    try:
        async with session.begin():
            row = (await session.execute(statement)).one_or_none()
            if row is None:
                raise HTTPException(status_code=403, detail={"code": "STAFF_ACCESS_REQUIRED"})
            values = row._mapping
            context = StaffContext(
                auth_user_id=identity.user_id,
                staff_id=values["staff_id"],
                business_id=values["business_id"],
                business_name=values["business_name"],
                role=StaffRole(values["role"]),
                timezone=values["timezone"],
                display_name=values["display_name"],
                username=values["username"],
                phone=values["phone"],
                must_change_password=values["must_change_password"],
            )
            if context.role in {StaffRole.MANAGER, StaffRole.ADMIN}:
                require_privileged_totp(
                    identity,
                    sensitive=(
                        request.method not in {"GET", "HEAD", "OPTIONS"}
                        and (request.method, getattr(request.scope.get("route"), "path", ""))
                        not in ROUTINE_STAFF_WRITES
                    ),
                )
                if get_settings().is_deployed:
                    active_factor = await session.scalar(
                        text("SELECT app_private.privileged_totp_active(:session_id,:user_id)"),
                        {
                            "session_id": uuid.UUID(str(identity.claims.get("session_id", ""))),
                            "user_id": identity.user_id,
                        },
                    )
                    if not active_factor:
                        raise HTTPException(403, detail={"code": "MFA_REQUIRED"})
            if context.must_change_password and request.url.path not in {
                "/api/v1/staff/context",
                "/api/v1/staff/profile",
            }:
                raise HTTPException(
                    status_code=403,
                    detail={"code": "PASSWORD_CHANGE_REQUIRED"},
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

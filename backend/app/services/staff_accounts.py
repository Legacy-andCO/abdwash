import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import StaffContext
from app.domain.enums import StaffRole
from app.domain.errors import ConflictError, DomainError
from app.domain.phones import normalize_phone_number
from app.domain.staff_usernames import normalize_staff_username
from app.integrations.supabase_admin import SupabaseAdminClient
from app.models.entities import AuditEvent, ScheduleResource, StaffProfile, TeamMembership
from app.schemas.staff import (
    OwnProfileUpdate,
    StaffAccountCreate,
    StaffAccountUpdate,
    StaffProfileView,
    TeamReference,
)


def _normalize_optional_phone(phone: str | None) -> str | None:
    if phone is None or not phone.strip():
        return None
    try:
        return normalize_phone_number(phone)
    except ValueError as exc:
        raise DomainError("INVALID_PHONE", str(exc), status_code=422) from exc


async def _profile_view(session: AsyncSession, profile: StaffProfile) -> StaffProfileView:
    teams = (
        await session.execute(
            select(ScheduleResource.id, ScheduleResource.name)
            .join(TeamMembership, TeamMembership.resource_id == ScheduleResource.id)
            .where(
                TeamMembership.staff_profile_id == profile.id,
                TeamMembership.is_active.is_(True),
            )
            .order_by(ScheduleResource.name)
        )
    ).all()
    return _profile_data(
        profile, [TeamReference(id=id, name=name) for id, name in teams]
    )


def _profile_data(
    profile: StaffProfile, teams: list[TeamReference]
) -> StaffProfileView:
    return StaffProfileView(
        id=profile.id,
        display_name=profile.display_name,
        username=profile.username,
        phone=profile.phone,
        role=profile.role,
        is_active=profile.is_active,
        teams=teams,
    )


async def get_own_profile(
    session: AsyncSession, context: StaffContext
) -> StaffProfileView:
    profile = (
        await session.scalars(
            select(StaffProfile).where(
                StaffProfile.id == context.staff_id,
                StaffProfile.business_id == context.business_id,
            )
        )
    ).one()
    return await _profile_view(session, profile)


async def update_own_profile(
    session: AsyncSession,
    context: StaffContext,
    request: OwnProfileUpdate,
    admin: SupabaseAdminClient | None,
) -> StaffProfileView:
    profile = (
        await session.scalars(
            select(StaffProfile)
            .where(
                StaffProfile.id == context.staff_id,
                StaffProfile.business_id == context.business_id,
            )
            .with_for_update()
        )
    ).one()
    if request.display_name is not None:
        profile.display_name = request.display_name.strip()
    if request.phone is not None:
        profile.phone = _normalize_optional_phone(request.phone)
    if request.password is not None:
        if admin is None:
            raise DomainError(
                "STAFF_AUTH_UNAVAILABLE",
                "Password updates are not configured.",
                status_code=503,
            )
        await admin.update_staff_user(profile.auth_user_id, password=request.password)
    _audit(session, context, "staff_updated", profile.id, {"self_update": True})
    await session.flush()
    return await _profile_view(session, profile)


async def list_staff_accounts(
    session: AsyncSession, context: StaffContext
) -> list[StaffProfileView]:
    profiles = list(
        (
            await session.scalars(
                select(StaffProfile)
                .where(StaffProfile.business_id == context.business_id)
                .order_by(StaffProfile.is_active.desc(), StaffProfile.display_name)
                .limit(200)
            )
        ).all()
    )
    if not profiles:
        return []
    rows = (
        await session.execute(
            select(
                TeamMembership.staff_profile_id,
                ScheduleResource.id,
                ScheduleResource.name,
            )
            .join(ScheduleResource, ScheduleResource.id == TeamMembership.resource_id)
            .where(
                TeamMembership.staff_profile_id.in_([profile.id for profile in profiles]),
                TeamMembership.is_active.is_(True),
            )
            .order_by(ScheduleResource.name)
        )
    ).all()
    teams_by_staff: dict[uuid.UUID, list[TeamReference]] = {}
    for staff_id, team_id, name in rows:
        teams_by_staff.setdefault(staff_id, []).append(TeamReference(id=team_id, name=name))
    return [_profile_data(profile, teams_by_staff.get(profile.id, [])) for profile in profiles]


def _validate_managed_role(actor: StaffContext, role: str) -> None:
    if role == StaffRole.ADMIN:
        raise DomainError(
            "ADMIN_CREATION_FORBIDDEN",
            "Admin accounts cannot be created here.",
            status_code=403,
        )
    if actor.role == StaffRole.MANAGER and role != StaffRole.EMPLOYEE:
        raise DomainError(
            "ROLE_MANAGEMENT_FORBIDDEN",
            "Managers can only manage employee accounts.",
            status_code=403,
        )


async def create_staff_account(
    session: AsyncSession,
    context: StaffContext,
    request: StaffAccountCreate,
    admin: SupabaseAdminClient,
) -> StaffProfileView:
    username = normalize_staff_username(request.username)
    _validate_managed_role(context, request.role)
    existing = await session.scalar(
        select(StaffProfile.id).where(StaffProfile.username == username)
    )
    if existing is not None:
        raise ConflictError("USERNAME_TAKEN", "That username is already in use.")
    auth_user_id = await admin.create_staff_user(username, request.temporary_password)
    profile = StaffProfile(
        business_id=context.business_id,
        auth_user_id=auth_user_id,
        username=username,
        display_name=request.display_name.strip(),
        phone=_normalize_optional_phone(request.phone),
        role=request.role,
        is_active=True,
    )
    session.add(profile)
    await session.flush()
    _audit(session, context, "staff_created", profile.id, {"role": request.role})
    return await _profile_view(session, profile)


async def update_staff_account(
    session: AsyncSession,
    context: StaffContext,
    staff_id: uuid.UUID,
    request: StaffAccountUpdate,
) -> StaffProfileView:
    profile = await _managed_profile(session, context, staff_id, lock=True)
    _validate_managed_role(context, profile.role)
    if request.role is not None:
        _validate_managed_role(context, request.role)
        profile.role = request.role
    if request.display_name is not None:
        profile.display_name = request.display_name.strip()
    if request.phone is not None:
        profile.phone = _normalize_optional_phone(request.phone)
    event = "staff_updated"
    if request.is_active is not None and request.is_active != profile.is_active:
        profile.is_active = request.is_active
        event = "staff_reactivated" if request.is_active else "staff_deactivated"
    _audit(session, context, event, profile.id, {})
    await session.flush()
    return await _profile_view(session, profile)


async def reset_staff_password(
    session: AsyncSession,
    context: StaffContext,
    staff_id: uuid.UUID,
    password: str,
    admin: SupabaseAdminClient,
) -> None:
    profile = await _managed_profile(session, context, staff_id)
    _validate_managed_role(context, profile.role)
    await admin.update_staff_user(profile.auth_user_id, password=password)
    _audit(session, context, "staff_password_reset", profile.id, {})


async def _managed_profile(
    session: AsyncSession,
    context: StaffContext,
    staff_id: uuid.UUID,
    *,
    lock: bool = False,
) -> StaffProfile:
    statement = select(StaffProfile).where(
        StaffProfile.id == staff_id,
        StaffProfile.business_id == context.business_id,
    )
    if lock:
        statement = statement.with_for_update()
    profile = (await session.scalars(statement)).one_or_none()
    if profile is None:
        raise DomainError("STAFF_NOT_FOUND", "Staff member not found.", status_code=404)
    if profile.id == context.staff_id:
        raise DomainError(
            "SELF_MANAGEMENT_FORBIDDEN",
            "Use your own profile settings for this account.",
            status_code=403,
        )
    return profile


def _audit(
    session: AsyncSession,
    context: StaffContext,
    event_type: str,
    entity_id: uuid.UUID,
    metadata: dict[str, object],
) -> None:
    session.add(
        AuditEvent(
            business_id=context.business_id,
            actor_auth_user_id=context.auth_user_id,
            event_type=event_type,
            entity_type="staff_profile",
            entity_id=entity_id,
            metadata_json=metadata,
        )
    )

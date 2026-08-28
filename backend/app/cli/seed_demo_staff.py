import asyncio
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import create_engine, create_session_factory
from app.domain.enums import StaffRole
from app.domain.staff_usernames import normalize_staff_username
from app.integrations.supabase_admin import SupabaseAdminClient
from app.models.entities import Business, StaffProfile


@dataclass(frozen=True)
class DemoStaff:
    username: str
    display_name: str
    role: StaffRole


DEMO_STAFF = (
    DemoStaff("manager", "Demo Manager", StaffRole.MANAGER),
    DemoStaff("employee", "Demo Employee", StaffRole.EMPLOYEE),
)


def require_seed_settings(settings: Settings) -> tuple[str, str, str]:
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL is required to seed demo staff.")
    if not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required to seed demo staff.")
    if not settings.demo_staff_password:
        raise RuntimeError("DEMO_STAFF_PASSWORD is required to seed demo staff.")
    return (
        settings.supabase_url.rstrip("/"),
        settings.supabase_service_role_key,
        settings.demo_staff_password,
    )


async def ensure_auth_user(
    client: httpx.AsyncClient,
    *,
    supabase_url: str,
    service_role_key: str,
    username: str,
    password: str,
) -> uuid.UUID:
    admin = SupabaseAdminClient(
        client,
        supabase_url=supabase_url,
        service_role_key=service_role_key,
    )
    return await admin.ensure_staff_user(username, password)


async def upsert_staff_profile(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    auth_user_id: uuid.UUID,
    demo: DemoStaff,
) -> StaffProfile:
    username = normalize_staff_username(demo.username)
    matches = list(
        (
            await session.scalars(
                select(StaffProfile)
                .where(
                    or_(
                        StaffProfile.username == username,
                        StaffProfile.auth_user_id == auth_user_id,
                    )
                )
                .with_for_update()
            )
        ).all()
    )
    if len({profile.id for profile in matches}) > 1:
        raise RuntimeError(f"Conflicting staff profiles exist for {username}.")
    profile = matches[0] if matches else None
    if profile is None:
        profile = StaffProfile(
            business_id=business_id,
            auth_user_id=auth_user_id,
            username=username,
            display_name=demo.display_name,
            role=demo.role,
            is_active=True,
        )
        session.add(profile)
    else:
        if profile.business_id != business_id:
            raise RuntimeError(f"Staff profile {username} belongs to another business.")
        profile.auth_user_id = auth_user_id
        profile.username = username
        profile.display_name = demo.display_name
        profile.role = demo.role
        profile.is_active = True
    await session.flush()
    return profile


async def seed_demo_staff(settings: Settings) -> None:
    supabase_url, service_role_key, password = require_seed_settings(settings)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20)) as client:
            auth_users = {
                demo.username: await ensure_auth_user(
                    client,
                    supabase_url=supabase_url,
                    service_role_key=service_role_key,
                    username=demo.username,
                    password=password,
                )
                for demo in DEMO_STAFF
            }
        async with factory() as session, session.begin():
            business = (
                await session.scalars(select(Business).where(Business.slug == "abdwash"))
            ).one_or_none()
            if business is None:
                raise RuntimeError("The Trifecta business must be seeded first.")
            for demo in DEMO_STAFF:
                await upsert_staff_profile(
                    session,
                    business_id=business.id,
                    auth_user_id=auth_users[demo.username],
                    demo=demo,
                )
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(seed_demo_staff(get_settings()))
    print("Demo manager: manager")
    print("Demo employee: employee")
    print("Password: configured through DEMO_STAFF_PASSWORD")


if __name__ == "__main__":
    main()

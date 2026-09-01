import uuid
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from sqlalchemy import CheckConstraint
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli.seed_demo_staff import (
    DEMO_STAFF,
    ensure_auth_user,
    require_seed_settings,
    upsert_staff_profile,
)
from app.core.config import Settings
from app.domain.enums import StaffRole
from app.domain.errors import DomainError
from app.domain.staff_usernames import normalize_staff_username, staff_synthetic_email
from app.integrations.supabase_admin import SupabaseAdminClient
from app.models.entities import StaffProfile


def test_staff_username_is_normalized_and_converted_to_synthetic_email() -> None:
    assert normalize_staff_username("  Manager ") == "manager"
    assert staff_synthetic_email(" Employee ") == (
        "employee@staff.abdwash.local"
    )


def test_invalid_staff_username_is_rejected() -> None:
    with pytest.raises(DomainError, match="Staff usernames"):
        normalize_staff_username("not an email@example.com")


async def test_existing_demo_auth_user_is_updated_idempotently() -> None:
    auth_user_id = uuid.uuid4()
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "users": [
                        {
                            "id": str(auth_user_id),
                            "email": "manager@staff.abdwash.local",
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"id": str(auth_user_id)})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await ensure_auth_user(
            client,
            supabase_url="https://example.supabase.co",
            service_role_key="private-service-role",
            username="Manager",
            password=str(uuid.uuid4()),
        )

    assert result == auth_user_id
    assert [request.method for request in requests] == ["GET", "PUT"]
    assert requests[1].url.path.endswith(f"/auth/v1/admin/users/{auth_user_id}")


def test_staff_username_has_database_duplicate_and_lowercase_protection() -> None:
    username_indexes = [
        index
        for index in StaffProfile.__table__.indexes
        if index.name == "uq_staff_profiles_username_ci"
    ]
    assert len(username_indexes) == 1
    assert username_indexes[0].unique is True
    assert any(
        isinstance(constraint, CheckConstraint)
        and "username = lower(username)" in str(constraint.sqltext)
        for constraint in StaffProfile.__table__.constraints
    )


@pytest.mark.parametrize(
    ("demo_index", "expected_role"),
    [(0, StaffRole.MANAGER), (1, StaffRole.EMPLOYEE)],
)
async def test_demo_profiles_are_created_with_expected_roles(
    demo_index: int, expected_role: StaffRole
) -> None:
    session = MagicMock(spec=AsyncSession)
    scalar_result = MagicMock()
    scalar_result.all.return_value = []
    session.scalars = AsyncMock(return_value=scalar_result)
    session.flush = AsyncMock()
    business_id = uuid.uuid4()
    auth_user_id = uuid.uuid4()

    profile = await upsert_staff_profile(
        session,
        business_id=business_id,
        auth_user_id=auth_user_id,
        demo=DEMO_STAFF[demo_index],
    )

    assert profile.business_id == business_id
    assert profile.auth_user_id == auth_user_id
    assert profile.username == DEMO_STAFF[demo_index].username
    assert profile.role == expected_role
    session.add.assert_called_once_with(profile)
    session.flush.assert_awaited_once()


async def test_conflicting_duplicate_demo_profiles_fail_clearly() -> None:
    session = MagicMock(spec=AsyncSession)
    first = StaffProfile(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        auth_user_id=uuid.uuid4(),
        username="manager",
        display_name="First",
        role=StaffRole.MANAGER,
    )
    second = StaffProfile(
        id=uuid.uuid4(),
        business_id=first.business_id,
        auth_user_id=uuid.uuid4(),
        username="manager",
        display_name="Second",
        role=StaffRole.MANAGER,
    )
    scalar_result = MagicMock()
    scalar_result.all.return_value = [first, second]
    session.scalars = AsyncMock(return_value=scalar_result)

    with pytest.raises(RuntimeError, match="Conflicting staff profiles"):
        await upsert_staff_profile(
            session,
            business_id=first.business_id,
            auth_user_id=first.auth_user_id,
            demo=DEMO_STAFF[0],
        )


@pytest.mark.parametrize(
    ("service_role_key", "password", "missing_name"),
    [
        (None, "password", "SUPABASE_SERVICE_ROLE_KEY"),
        ("service-role", None, "DEMO_STAFF_PASSWORD"),
    ],
)
def test_demo_seed_requires_private_configuration(
    service_role_key: str | None, password: str | None, missing_name: str
) -> None:
    settings = Settings(
        _env_file=None,
        supabase_url="https://example.supabase.co",
        supabase_service_role_key=service_role_key,
        demo_staff_password=password,
    )
    with pytest.raises(RuntimeError, match=missing_name):
        require_seed_settings(settings)


async def test_customer_auth_identity_deletion_uses_server_side_admin_api() -> None:
    user_id = uuid.uuid4()
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        admin = SupabaseAdminClient(
            client,
            supabase_url="https://example.supabase.co",
            service_role_key="private-service-role",
        )
        await admin.delete_customer_user(user_id)

    assert len(requests) == 1
    assert requests[0].method == "DELETE"
    assert requests[0].url.path == f"/auth/v1/admin/users/{user_id}"
    assert requests[0].headers["authorization"] == "Bearer private-service-role"

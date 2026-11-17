"""Real PostgreSQL roles, real signed JWTs, synthetic identities and two tenants.

Only SECURITY_TEST_DATABASE_URL on loopback, with 'security_boundary_test' in its
name, is accepted. This module never falls back to DATABASE_URL.
"""

import asyncio
import json
import os
import re
import uuid
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import jwt
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.sessions import require_active_session
from app.auth.verifier import AuthenticationError, SupabaseTokenVerifier, VerifiedIdentity
from app.core.config import Settings
from app.domain.errors import DomainError
from app.main import app
from app.models.entities import (
    Business,
    BusinessSettings,
    CustomerProfile,
    ScheduleResource,
    Service,
    ServicePrice,
    StaffProfile,
    TeamMembership,
)
from app.repositories.business import DEFAULT_BUSINESS_SLUG
from app.services.api_rate_limits import consume_api_attempt
from app.services.policy_acceptance import POLICY_REVISION

URL = os.getenv("SECURITY_TEST_DATABASE_URL")
PARSED = make_url(URL) if URL else None
SAFE = (
    PARSED is not None
    and PARSED.host in {"localhost", "127.0.0.1", "::1"}
    and "security_boundary_test" in (PARSED.database or "")
)
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.asyncio(loop_scope="module"),
    pytest.mark.skipif(not SAFE, reason="A dedicated local SECURITY_TEST_DATABASE_URL is required"),
]
SECRET = "synthetic-only-audit-signing-key-" + "x" * 32


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def boundary():
    assert SAFE and URL
    engine = create_async_engine(URL)
    async with engine.begin() as conn:
        # SAFE above restricts this reset to the explicitly dedicated synthetic database.
        for schema in ("app_private", "public", "auth"):
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
        await conn.execute(
            text(
                "CREATE TABLE auth.mfa_factors(id uuid PRIMARY KEY,user_id uuid,factor_type text,status text)"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS auth.users(id uuid PRIMARY KEY, email_confirmed_at timestamptz, banned_until timestamptz, deleted_at timestamptz, is_anonymous boolean DEFAULT false)"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS auth.sessions(id uuid PRIMARY KEY, factor_id uuid, user_id uuid REFERENCES auth.users(id), not_after timestamptz)"
            )
        )

        def migrate(sync):
            config = Config("alembic.ini")
            config.attributes["connection"] = sync
            command.upgrade(config, "head")

        await conn.run_sync(migrate)
    owner = async_sessionmaker(engine, expire_on_commit=False)
    runtime_engine = create_async_engine(
        URL, connect_args={"server_settings": {"role": "trifecta_runtime"}}
    )
    runtime = async_sessionmaker(runtime_engine, expire_on_commit=False, autoflush=False)
    actors = {
        name: uuid.uuid4()
        for name in ("a", "b", "employee", "other_employee", "manager", "admin", "foreign_manager")
    }
    sessions = {name: uuid.uuid4() for name in actors}
    async with owner() as db, db.begin():
        for name, user_id in actors.items():
            await db.execute(
                text("INSERT INTO auth.users(id,email_confirmed_at) VALUES (:id,now())"),
                {"id": user_id},
            )
            await db.execute(
                text("INSERT INTO auth.sessions(id,user_id) VALUES (:sid,:uid)"),
                {"sid": sessions[name], "uid": user_id},
            )
        businesses = [
            Business(name="Synthetic A", slug=DEFAULT_BUSINESS_SLUG),
            Business(name="Synthetic B", slug="audit-foreign"),
        ]
        db.add_all(businesses)
        await db.flush()
        for business in businesses:
            db.add(
                BusinessSettings(
                    business_id=business.id,
                    timezone="Asia/Dubai",
                    currency_code="AED",
                    opening_time=time(9),
                    closing_time=time(21),
                    slot_duration_minutes=120,
                    cancellation_cutoff_hours=24,
                )
            )
        teams = [
            ScheduleResource(business_id=businesses[0].id, name="A1", resource_type="mobile_team"),
            ScheduleResource(business_id=businesses[0].id, name="A2", resource_type="mobile_team"),
            ScheduleResource(business_id=businesses[1].id, name="B1", resource_type="mobile_team"),
        ]
        service = Service(
            business_id=businesses[0].id,
            name="Synthetic Wash",
            price_minor=5000,
            estimated_duration_minutes=120,
        )
        db.add_all([*teams, service])
        await db.flush()
        db.add(
            ServicePrice(
                business_id=businesses[0].id,
                service_id=service.id,
                vehicle_type="sedan",
                price_minor=5000,
            )
        )
        profiles = {}
        for name in ("a", "b"):
            profile = CustomerProfile(
                business_id=businesses[0].id,
                auth_user_id=actors[name],
                first_name=f"Synthetic {name}",
                surname="Audit",
                email=f"{name}@example.com",
                phone="+971501234567",
            )
            db.add(profile)
            profiles[name] = profile
        staff = {}
        for name in ("employee", "other_employee", "manager", "admin", "foreign_manager"):
            role = "employee" if "employee" in name else "admin" if name == "admin" else "manager"
            person = StaffProfile(
                business_id=businesses[1 if name == "foreign_manager" else 0].id,
                auth_user_id=actors[name],
                username=f"audit.{name}",
                display_name=name,
                role=role,
            )
            db.add(person)
            staff[name] = person
        await db.flush()
        db.add_all(
            [
                TeamMembership(resource_id=teams[i].id, staff_profile_id=staff[name].id)
                for i, name in [(0, "employee"), (1, "other_employee"), (2, "foreign_manager")]
            ]
        )
    config = Settings(
        _env_file=None,
        app_env="test",
        supabase_url="https://audit.supabase.co",
        supabase_jwt_secret=SECRET,
    )
    signed = {
        name: jwt.encode(
            {
                "sub": str(user),
                "session_id": str(sessions[name]),
                "aud": "authenticated",
                "iss": config.supabase_issuer,
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "email": f"{name}@example.com",
                "user_metadata": {"role": "admin"},
                "aal": "aal2",
                "amr": [{"method": "totp", "timestamp": datetime.now(UTC).timestamp()}],
            },
            SECRET,
            algorithm="HS256",
        )
        for name, user in actors.items()
    }
    saved = dict(app.state._state)
    async with httpx.AsyncClient() as provider:
        app.state.session_factory = runtime
        app.state.auth_verifier = SupabaseTokenVerifier(config, provider)
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://audit"
            ) as client:
                yield SimpleNamespace(
                    client=client,
                    owner=owner,
                    runtime=runtime,
                    actors=actors,
                    sessions=sessions,
                    tokens=signed,
                    profiles=profiles,
                    teams=teams,
                    service=service,
                    businesses=businesses,
                )
        finally:
            app.state._state.clear()
            app.state._state.update(saved)
    await runtime_engine.dispose()
    await engine.dispose()


def headers(f, actor="manager", key=None):
    return {
        "Authorization": f"Bearer {f.tokens[actor]}",
        "Idempotency-Key": str(key or uuid.uuid4()),
    }


def booking_payload(f, day, overlap=None):
    return {
        "date": day,
        "time": "09:00",
        "contact": {"first_name": "Synthetic", "phone": "+971501234567"},
        "location": {"written_address": "Synthetic address", "instructions": "Test only"},
        "vehicles": [{"service_id": str(f.service.id), "vehicle_type": "sedan"}],
        "expected_amount_minor": 5000,
        "policy_revision": POLICY_REVISION,
        "policy_delivery": "provided",
        **({"overlap": {"team_id": str(overlap), "confirmed": True}} if overlap else {}),
    }


async def test_all_protected_endpoints_reject_anonymous(boundary):
    results = []
    inventory = json.loads(
        (Path(__file__).parents[2] / "docs/security-audit/evidence/endpoints.json").read_text()
    )
    for route in inventory:
        if not route["path"].startswith(("/api/v1/staff/", "/api/v1/customer/")):
            continue
        path = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), route["path"])
        response = await boundary.client.request(
            route["method"],
            path,
            json={} if route["method"] in {"POST", "PUT", "PATCH", "DELETE"} else None,
        )
        results.append(
            {
                "method": route["method"],
                "path": route["path"],
                "anonymous_status": response.status_code,
                "result": "PASS" if response.status_code == 401 else "FAIL",
            }
        )
    out = (
        Path(__file__).parents[2]
        / "docs/security-audit/follow-up/local-endpoint-anonymous-results.json"
    )
    out.write_text(json.dumps(results, indent=2))
    assert results and all(r["result"] == "PASS" for r in results), [
        r for r in results if r["result"] != "PASS"
    ]


async def test_every_business_table_denies_client_roles_and_runtime_cannot_truncate(boundary):
    async with boundary.owner() as db:
        tables = list(
            (
                await db.scalars(
                    text(
                        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
                    )
                )
            ).all()
        )
    outcomes = []
    for role in ("anon", "authenticated"):
        for table in tables:
            async with boundary.owner() as db:
                column = await db.scalar(
                    text(
                        "SELECT attname FROM pg_attribute WHERE attrelid=to_regclass(:table) AND attnum>0 AND NOT attisdropped ORDER BY attnum LIMIT 1"
                    ),
                    {"table": f"public.{table}"},
                )
            for operation in (
                f'SELECT * FROM public."{table}" LIMIT 1',
                f'DELETE FROM public."{table}" WHERE false',
                f'UPDATE public."{table}" SET "{column}"="{column}" WHERE false',
                f'INSERT INTO public."{table}" DEFAULT VALUES',
                f'TRUNCATE public."{table}"',
            ):
                async with boundary.owner() as db, db.begin():
                    await db.execute(text(f"SET LOCAL ROLE {role}"))
                    with pytest.raises(DBAPIError) as error:
                        await db.execute(text(operation))
                    assert getattr(error.value.orig, "sqlstate", None) == "42501", str(error.value)
            outcomes.append(
                {
                    "table": table,
                    "role": role,
                    "select": "PASS",
                    "insert": "PASS",
                    "update": "PASS",
                    "delete": "PASS",
                    "truncate": "PASS",
                }
            )
    async with boundary.runtime() as db, db.begin():
        assert await db.scalar(text("SELECT count(*) FROM public.customer_profiles")) == 2
        with pytest.raises(DBAPIError):
            await db.execute(text("TRUNCATE public.customer_profiles CASCADE"))
    (
        Path(__file__).parents[2] / "docs/security-audit/follow-up/local-role-results.json"
    ).write_text(json.dumps(outcomes, indent=2))


async def test_customer_ownership_and_metadata_cannot_grant_staff_access(boundary):
    f = boundary
    created = await f.client.post(
        "/api/v1/customer/addresses",
        headers=headers(f, "a"),
        json={
            "label": "Home",
            "written_address": "Synthetic private home",
            "location_url": "https://www.google.com/maps?q=25,55",
            "instructions": "Synthetic gate",
            "is_default": True,
        },
    )
    assert created.status_code == 201, created.text
    address_id = created.json()["id"]
    denied = await f.client.delete(
        f"/api/v1/customer/addresses/{address_id}", headers=headers(f, "b")
    )
    assert denied.status_code == 404
    own = await f.client.get("/api/v1/customer/addresses", headers=headers(f, "a"))
    assert address_id in own.text
    assert (await f.client.get("/api/v1/staff/context", headers=headers(f, "a"))).status_code == 403
    assert (
        await f.client.get("/api/v1/staff/users", headers=headers(f, "employee"))
    ).status_code == 403


async def test_aal1_privileged_access_and_removed_factors_are_rejected(boundary, monkeypatch):
    f = boundary
    claims = jwt.decode(
        f.tokens["manager"], SECRET, algorithms=["HS256"], options={"verify_aud": False}
    )
    claims["aal"] = "aal1"
    token = jwt.encode(claims, SECRET, algorithm="HS256")
    for path in [
        "/api/v1/staff/context",
        "/api/v1/staff/users",
        "/api/v1/staff/teams",
        "/api/v1/staff/calendar-bookings/catalogue",
    ]:
        response = await f.client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403 and response.json()["detail"]["code"] == "MFA_REQUIRED"
    factor = uuid.uuid4()
    async with f.owner() as db, db.begin():
        await db.execute(
            text("INSERT INTO auth.mfa_factors VALUES (:factor,:uid,'totp','verified')"),
            {"factor": factor, "uid": f.actors["manager"]},
        )
        await db.execute(
            text("UPDATE auth.sessions SET factor_id=:factor WHERE id=:sid"),
            {"factor": factor, "sid": f.sessions["manager"]},
        )
    monkeypatch.setattr(
        "app.auth.dependencies.get_settings", lambda: SimpleNamespace(is_deployed=True)
    )
    assert (await f.client.get("/api/v1/staff/context", headers=headers(f))).status_code == 200
    async with f.owner() as db, db.begin():
        await db.execute(text("DELETE FROM auth.mfa_factors WHERE id=:id"), {"id": factor})
    assert (await f.client.get("/api/v1/staff/context", headers=headers(f))).status_code == 403


async def test_role_promotion_cannot_grandfather_an_aal1_employee_session(boundary):
    f = boundary
    claims = jwt.decode(
        f.tokens["employee"], SECRET, algorithms=["HS256"], options={"verify_aud": False}
    )
    claims["aal"] = "aal1"
    claims["amr"] = [{"method": "password", "timestamp": datetime.now(UTC).timestamp()}]
    token = jwt.encode(claims, SECRET, algorithm="HS256")
    auth = {"Authorization": f"Bearer {token}"}
    assert (await f.client.get("/api/v1/staff/context", headers=auth)).status_code == 200
    async with f.owner() as db, db.begin():
        await db.execute(
            text("UPDATE staff_profiles SET role='manager' WHERE auth_user_id=:id"),
            {"id": f.actors["employee"]},
        )
    try:
        assert (await f.client.get("/api/v1/staff/context", headers=auth)).status_code == 403
    finally:
        async with f.owner() as db, db.begin():
            await db.execute(
                text("UPDATE staff_profiles SET role='employee' WHERE auth_user_id=:id"),
                {"id": f.actors["employee"]},
            )


async def test_employee_cannot_read_another_teams_member_directory(boundary):
    f = boundary
    own = await f.client.get(f"/api/v1/staff/teams/{f.teams[0].id}", headers=headers(f, "employee"))
    assert own.status_code == 200
    denied = await f.client.get(
        f"/api/v1/staff/teams/{f.teams[1].id}", headers=headers(f, "employee")
    )
    assert denied.status_code == 404


async def test_old_employee_session_cannot_change_its_password(boundary, monkeypatch):
    f = boundary
    calls = []

    class SyntheticAuthAdmin:
        async def update_staff_user(self, user_id, **kwargs):
            calls.append(user_id)

    monkeypatch.setattr("app.api.staff._admin", lambda request: SyntheticAuthAdmin())
    claims = jwt.decode(
        f.tokens["employee"], SECRET, algorithms=["HS256"], options={"verify_aud": False}
    )
    claims["aal"] = "aal1"
    claims["amr"] = [{"method": "password", "timestamp": datetime.now(UTC).timestamp() - 600}]
    token = jwt.encode(claims, SECRET, algorithm="HS256")
    response = await f.client.patch(
        "/api/v1/staff/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"password": "Synthetic-Replacement-123!"},
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "REAUTHENTICATION_REQUIRED"
    assert calls == []
    claims["amr"] = [{"method": "password", "timestamp": datetime.now(UTC).timestamp()}]
    recent = jwt.encode(claims, SECRET, algorithm="HS256")
    legitimate = await f.client.patch(
        "/api/v1/staff/profile",
        headers={"Authorization": f"Bearer {recent}"},
        json={"password": "Synthetic-Replacement-123!"},
    )
    assert legitimate.status_code == 200, legitimate.text
    assert calls == [f.actors["employee"]]


async def test_staff_overlap_is_scoped_idempotent_and_does_not_displace_original(boundary):
    f = boundary
    payload = booking_payload(f, "2037-03-10")
    first = await f.client.post(
        "/api/v1/staff/calendar-bookings", headers=headers(f, "employee"), json=payload
    )
    assert first.status_code == 201, first.text
    receipt = first.json()
    original = (
        await f.client.get(
            f"/api/v1/staff/jobs/{receipt['job_id']}", headers=headers(f, "employee")
        )
    ).json()
    assert (
        await f.client.get(
            f"/api/v1/staff/jobs/{receipt['job_id']}", headers=headers(f, "other_employee")
        )
    ).status_code == 404
    assert (
        await f.client.get(
            f"/api/v1/staff/jobs/{receipt['job_id']}", headers=headers(f, "foreign_manager")
        )
    ).status_code == 404
    key = uuid.uuid4()
    overlap = booking_payload(f, "2037-03-10", f.teams[0].id)
    overlap["overlap"].update(
        {"job_id": receipt["job_id"], "expected_version": original["version"]}
    )
    endpoint = f"/api/v1/staff/calendar-bookings/{receipt['job_id']}/double-book"
    assert (
        await f.client.post(
            "/api/v1/staff/calendar-bookings", headers=headers(f, "employee"), json=overlap
        )
    ).status_code == 422
    second = await f.client.post(endpoint, headers=headers(f, "employee", key), json=overlap)
    assert second.status_code == 201, second.text
    retry = await f.client.post(endpoint, headers=headers(f, "employee", key), json=overlap)
    assert retry.json() == second.json()
    unchanged = (
        await f.client.get(
            f"/api/v1/staff/jobs/{receipt['job_id']}", headers=headers(f, "employee")
        )
    ).json()
    assert unchanged == original
    assert (await f.client.post(endpoint, headers=headers(f, "a"), json=overlap)).status_code == 403
    assert (
        await f.client.post(endpoint, headers=headers(f, "other_employee"), json=overlap)
    ).status_code == 404


async def test_customer_booking_idor_mass_assignment_and_unavailable_payments(boundary):
    from test_public_schemas import valid_booking_payload

    f = boundary
    hold = await f.client.post(
        "/api/v1/public/holds",
        json={
            "date": "2038-04-12",
            "start_time": "09:00",
            "vehicle_count": 1,
            "service_ids": [str(f.service.id)],
        },
    )
    assert hold.status_code == 201, hold.text
    payload = valid_booking_payload()
    payload["hold_token"] = hold.json()["hold_token"]
    payload["vehicles"][0]["service_id"] = str(f.service.id)
    payload["policy_acceptance"] = {"accepted": True, "language": "en", "revision": POLICY_REVISION}
    url = "/api/v1/public/bookings"
    assert (
        await f.client.post(
            url,
            headers=headers(f, "a"),
            json={**payload, "total_amount_minor": 0, "payment_status": "paid"},
        )
    ).status_code == 422
    assert (
        await f.client.post(
            url, headers=headers(f, "a"), json={**payload, "payment_choice": "pay_now"}
        )
    ).status_code == 503
    created = await f.client.post(url, headers=headers(f, "a"), json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["total_amount_minor"] == 5000
    booking_id = created.json()["id"]
    owned = f"/api/v1/customer/bookings/{booking_id}"
    assert (await f.client.get(owned, headers=headers(f, "a"))).status_code == 200
    assert (await f.client.get(owned, headers=headers(f, "b"))).status_code == 404
    assert (
        await f.client.post(
            owned + "/cancellation-requests",
            headers=headers(f, "b"),
            json={"reason": "Synthetic attempt"},
        )
    ).status_code == 404
    assert (
        await f.client.get(
            f"/api/v1/staff/customers/{f.profiles['a'].id}", headers=headers(f, "foreign_manager")
        )
    ).status_code == 404
    injection = await f.client.get(
        "/api/v1/staff/jobs", headers=headers(f), params={"scope": "all", "search": "' OR 1=1;--"}
    )
    assert injection.status_code == 200 and injection.json()["jobs"] == []
    revoke = f"/api/v1/staff/bookings/{booking_id}/guest-access/revoke"
    assert (await f.client.post(revoke)).status_code == 401
    assert (await f.client.post(revoke, headers=headers(f, "employee"))).status_code == 403
    assert (await f.client.post(revoke, headers=headers(f, "foreign_manager"))).status_code == 404
    assert (await f.client.post(revoke, headers=headers(f))).status_code == 204
    denied = await f.client.get(
        "/api/v1/public/bookings/manage",
        headers={"X-Booking-Management-Token": created.json()["management_token"]},
    )
    assert denied.status_code == 404
    async with f.owner() as db:
        assert (
            await db.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE event_type='guest_access_revoked' AND entity_id=:id"
                ),
                {"id": uuid.UUID(booking_id)},
            )
            == 1
        )


async def test_inactive_customer_cannot_reactivate_itself_by_updating_profile(boundary):
    f = boundary
    async with f.owner() as db, db.begin():
        await db.execute(
            text("UPDATE public.customer_profiles SET is_active=false WHERE id=:id"),
            {"id": f.profiles["a"].id},
        )
    try:
        response = await f.client.patch(
            "/api/v1/customer/profile",
            headers=headers(f, "a"),
            json={"first_name": "Synthetic", "surname": "Audit", "phone": "+971501234567"},
        )
        assert response.status_code == 409
        async with f.owner() as db:
            assert (
                await db.scalar(
                    text("SELECT is_active FROM public.customer_profiles WHERE id=:id"),
                    {"id": f.profiles["a"].id},
                )
                is False
            )
    finally:
        async with f.owner() as db, db.begin():
            await db.execute(
                text("UPDATE public.customer_profiles SET is_active=true WHERE id=:id"),
                {"id": f.profiles["a"].id},
            )


async def test_expired_idempotency_key_can_be_reused_without_unique_key_failure(boundary):
    from app.services.idempotency import find_idempotent_response, store_idempotent_response

    args = {
        "scope": "synthetic-expiry",
        "operation": "test",
        "key": "synthetic-retry-key",
        "request_hash": "x" * 64,
    }
    async with boundary.runtime() as db, db.begin():
        store_idempotent_response(
            db, **args, response_status=201, response_json={"synthetic": True}, resource_id=None
        )
        await db.flush()
        await db.execute(
            text(
                "UPDATE public.idempotency_records SET expires_at=now()-interval '1 second' WHERE scope=:scope"
            ),
            {"scope": args["scope"]},
        )
    async with boundary.runtime() as db, db.begin():
        assert await find_idempotent_response(db, **args) is None
        store_idempotent_response(
            db, **args, response_status=201, response_json={"synthetic": True}, resource_id=None
        )
    async with boundary.runtime() as db:
        assert (
            await db.scalar(
                text("SELECT count(*) FROM public.idempotency_records WHERE scope=:scope"),
                {"scope": args["scope"]},
            )
            == 1
        )


async def test_authoritative_sessions_reject_revoked_banned_and_unverified_identities(
    boundary, monkeypatch
):
    f = boundary
    identity = VerifiedIdentity(f.actors["a"], {"session_id": str(f.sessions["a"])})
    monkeypatch.setattr(
        "app.auth.dependencies.get_settings", lambda: SimpleNamespace(is_deployed=True)
    )
    assert (
        await f.client.get("/api/v1/customer/addresses", headers=headers(f, "a"))
    ).status_code == 200
    async with f.runtime() as db:
        await require_active_session(db, identity)
    for sql in [
        "UPDATE auth.users SET banned_until=now()+interval '1 hour' WHERE id=:id",
        "UPDATE auth.users SET banned_until=NULL,email_confirmed_at=NULL WHERE id=:id",
        "DELETE FROM auth.sessions WHERE user_id=:id",
    ]:
        async with f.owner() as db, db.begin():
            await db.execute(text(sql), {"id": f.actors["a"]})
        async with f.runtime() as db:
            with pytest.raises(AuthenticationError):
                await require_active_session(db, identity)
        assert (
            await f.client.get("/api/v1/customer/addresses", headers=headers(f, "a"))
        ).status_code == 401


async def test_shared_rate_limits_are_atomic_and_ipv6_rotation_cannot_reset_them(boundary):
    async def attempt(peer):
        try:
            async with boundary.runtime() as db, db.begin():
                await consume_api_attempt(db, "synthetic", peer, write=True)
            return True
        except DomainError as error:
            assert error.status_code == 429
            return False

    results = await asyncio.gather(*(attempt(f"2001:db8::{'%x' % (i + 1)}") for i in range(20)))
    assert sum(results) == 12


async def test_migration_downgrade_and_upgrade_preserve_customer_rows(boundary):
    async with boundary.owner() as db:
        before = await db.scalar(text("SELECT count(*) FROM public.customer_profiles"))
    async with boundary.owner() as db, db.begin():
        conn = await db.connection()

        def roundtrip(sync):
            config = Config("alembic.ini")
            config.attributes["connection"] = sync
            command.downgrade(config, "a83b97c41d62")
            command.upgrade(config, "head")

        await conn.run_sync(roundtrip)
    async with boundary.owner() as db:
        assert await db.scalar(text("SELECT count(*) FROM public.customer_profiles")) == before

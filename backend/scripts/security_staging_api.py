"""Real native JWT -> FastAPI ASGI -> restricted staging SQL login.

No authentication/dependency mocks. This is an in-process API integration run,
not a hosted deployment or browser/device test. Configuration never reads .env.
"""

import asyncio
import json
import os
import secrets
import uuid
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from urllib.parse import quote

import certifi
import httpx
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from security_staging_probe import CONFIG, ROOT, Probe


def configure():
    from app.core.config import Settings, get_settings

    d = json.loads(CONFIG.read_text())
    if (
        d["project_ref"] != "mgfzfgvlrxwyyftwukwf"
        or d["db_host"] != "aws-0-eu-central-1.pooler.supabase.com"
        or d["db_user"] != "trifecta_staging_api.mgfzfgvlrxwyyftwukwf"
    ):
        raise RuntimeError("Only the isolated staging project and restricted login are permitted")
    for key in ("management_signing_key", "dispatch_secret"):
        d.setdefault(key, secrets.token_urlsafe(40))
    CONFIG.write_text(json.dumps(d), encoding="utf-8")
    bundle = ROOT / "tmp/staging-ca-bundle.pem"
    bundle.write_bytes(
        Path(certifi.where()).read_bytes()
        + b"\n"
        + (ROOT / "tmp/supabase-prod-ca-2021.crt").read_bytes()
    )
    os.environ["SSL_CERT_FILE"] = str(bundle)
    # Clear only application field names in this child process; do not inherit
    # live integration values or permit .env fallback during the probe.
    for field in Settings.model_fields:
        os.environ.pop(field.upper(), None)
    Settings.model_config["env_file"] = None
    values = {
        "APP_ENV": "staging",
        "DATABASE_URL": f"postgresql+asyncpg://{quote(d['db_user'])}:{d['runtime_password']}@{d['db_host']}:5432/postgres",
        "DB_REQUIRE_TLS": "true",
        "DB_DISABLE_PREPARED_STATEMENTS": "true",
        "SUPABASE_URL": d["url"],
        "BOOKING_MANAGEMENT_SIGNING_KEY": d["management_signing_key"],
        "OUTBOX_DISPATCH_SECRET": d["dispatch_secret"],
        "VERIFIED_COMPLAINTS_INBOX": "complaints@security.example.com",
        "CORS_ORIGINS": '["https://staging-web.example.com"]',
        "PUBLIC_WEB_URL": "https://staging-web.example.com",
        "LOG_LEVEL": "WARNING",
    }
    os.environ.update(values)
    get_settings.cache_clear()
    return get_settings()


async def seed(session_factory, p):
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

    async with session_factory() as db, db.begin():
        existing = list(await db.scalars(select(Business)))
        if existing:
            if not all(b.name.startswith("Synthetic") for b in existing):
                raise RuntimeError("Staging contains unexpected non-synthetic business records")
            return p.config["fixtures"]
        businesses = [
            Business(name="Synthetic Security A", slug=DEFAULT_BUSINESS_SLUG),
            Business(name="Synthetic Security B", slug="security-staging-b"),
        ]
        db.add_all(businesses)
        await db.flush()
        for b in businesses:
            db.add(
                BusinessSettings(
                    business_id=b.id,
                    timezone="Asia/Dubai",
                    currency_code="AED",
                    opening_time=time(9),
                    closing_time=time(21),
                    slot_duration_minutes=120,
                    cancellation_cutoff_hours=24,
                )
            )
        teams = [
            ScheduleResource(
                business_id=businesses[0].id, name="Synthetic A1", resource_type="mobile_team"
            ),
            ScheduleResource(
                business_id=businesses[0].id, name="Synthetic A2", resource_type="mobile_team"
            ),
            ScheduleResource(
                business_id=businesses[1].id, name="Synthetic B1", resource_type="mobile_team"
            ),
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
        staff = {}
        for name, uid in p.config["users"].items():
            if name.startswith("customer_"):
                person = CustomerProfile(
                    business_id=businesses[0].id,
                    auth_user_id=uuid.UUID(uid),
                    first_name="Synthetic",
                    surname=name,
                    email=name + "@security.example.com",
                    phone="+971500000000",
                )
                profiles[name] = person
            else:
                role = (
                    "employee"
                    if "employee" in name
                    else "admin"
                    if name.startswith("admin")
                    else "manager"
                )
                person = StaffProfile(
                    business_id=businesses[1 if name == "foreign_manager" else 0].id,
                    auth_user_id=uuid.UUID(uid),
                    username="audit." + name,
                    display_name="Synthetic " + name,
                    role=role,
                )
                staff[name] = person
            db.add(person)
        await db.flush()
        for i, name in [(0, "employee"), (1, "other_employee"), (2, "foreign_manager")]:
            db.add(TeamMembership(resource_id=teams[i].id, staff_profile_id=staff[name].id))
        fixture = {
            "businesses": [str(x.id) for x in businesses],
            "teams": [str(x.id) for x in teams],
            "service": str(service.id),
            "profiles": {k: str(v.id) for k, v in profiles.items()},
            "staff": {k: str(v.id) for k, v in staff.items()},
        }
    p.config["fixtures"] = fixture
    p.save()
    return fixture


async def main():
    settings = configure()
    settings.log_level = "INFO"
    from app.main import app
    from app.services.policy_acceptance import POLICY_REVISION

    p = Probe(ROOT / "docs/security-audit/follow-up/staging-api.json")
    try:
        async with app.router.lifespan_context(app):
            f = await seed(app.state.session_factory, p)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="https://staging-api.example.com"
            ) as api:

                def h(actor="manager", aal=2, key=None):
                    sessions = p.config["aal2_sessions"] if aal == 2 else p.config["aal1_sessions"]
                    return {
                        "Authorization": "Bearer " + sessions[actor]["access_token"],
                        "Idempotency-Key": key or str(uuid.uuid4()),
                    }

                for actor in ("manager", "admin", "admin_two", "foreign_manager"):
                    r = await api.get("/api/v1/staff/context", headers=h(actor, 1))
                    p.check(
                        "native aal1 privileged API denied " + actor,
                        r.status_code == 403,
                        http_status=r.status_code,
                    )
                    # Refresh preserves native assurance, unlike a new login.
                    refreshed = await p.auth(
                        "POST",
                        "/token?grant_type=refresh_token",
                        json={"refresh_token": p.config["aal2_sessions"][actor]["refresh_token"]},
                    )
                    if refreshed.status_code == 200:
                        p.config["aal2_sessions"][actor] = refreshed.json()
                    r = await api.get("/api/v1/staff/context", headers=h(actor))
                    p.check(
                        "native aal2 privileged API allowed " + actor,
                        r.status_code == 200,
                        http_status=r.status_code,
                    )
                r = await api.get("/api/v1/staff/context", headers=h("employee", 1))
                p.check(
                    "employee retains aal1 access", r.status_code == 200, http_status=r.status_code
                )
                r = await api.get("/api/v1/staff/context", headers=h("customer_a", 1))
                p.check(
                    "customer cannot become staff", r.status_code == 403, http_status=r.status_code
                )
                async with app.state.session_factory() as db, db.begin():
                    await db.execute(
                        text("UPDATE staff_profiles SET role='manager' WHERE id=:id"),
                        {"id": uuid.UUID(f["staff"]["employee"])},
                    )
                r = await api.get("/api/v1/staff/context", headers=h("employee", 1))
                p.check(
                    "authoritative promotion immediately enforces MFA",
                    r.status_code == 403,
                    http_status=r.status_code,
                )
                async with app.state.session_factory() as db, db.begin():
                    await db.execute(
                        text("UPDATE staff_profiles SET role='employee' WHERE id=:id"),
                        {"id": uuid.UUID(f["staff"]["employee"])},
                    )
                for i, status in [(0, 200), (1, 404), (2, 404)]:
                    r = await api.get(
                        "/api/v1/staff/teams/" + f["teams"][i], headers=h("employee", 1)
                    )
                    p.check(
                        "employee team boundary " + str(i),
                        r.status_code == status,
                        http_status=r.status_code,
                    )
                address = {
                    "label": "Synthetic home",
                    "written_address": "Synthetic staging address",
                    "location_url": "https://maps.google.com/?q=Dubai",
                    "instructions": "Synthetic fixture",
                }
                r = await api.post(
                    "/api/v1/customer/addresses", headers=h("customer_a", 1), json=address
                )
                p.check("customer address create", r.status_code == 201, http_status=r.status_code)
                if r.status_code == 201:
                    aid = r.json()["id"]
                    r = await api.delete(
                        "/api/v1/customer/addresses/" + aid, headers=h("customer_b", 1)
                    )
                    p.check(
                        "customer address IDOR denied",
                        r.status_code == 404,
                        http_status=r.status_code,
                    )

                # Intentional employee overlap must preserve the first appointment.
                async def unused_date(offset):
                    for delta in range(offset, offset + 365):
                        candidate = (datetime.now(UTC) + timedelta(days=delta)).date()
                        async with app.state.session_factory() as db:
                            used = await db.scalar(
                                text(
                                    "SELECT EXISTS(SELECT FROM bookings WHERE scheduled_start::date=:day) OR EXISTS(SELECT FROM slot_hold_groups WHERE slot_start::date=:day)"
                                ),
                                {"day": candidate},
                            )
                        if not used:
                            return candidate.isoformat()
                    raise RuntimeError("No unused synthetic test date; no data was deleted")

                day = await unused_date(45)
                payload = {
                    "date": day,
                    "time": "09:00",
                    "contact": {
                        "first_name": "Synthetic",
                        "surname": "Staff",
                        "email": "staff_booking@security.example.com",
                        "phone": "+971500000000",
                    },
                    "location": {
                        "written_address": "Synthetic staging",
                        "instructions": "Synthetic fixture",
                    },
                    "vehicles": [
                        {
                            "make": "Test",
                            "model": "Synthetic",
                            "vehicle_type": "sedan",
                            "plate_number": "AUDIT 1",
                            "service_id": f["service"],
                        }
                    ],
                    "expected_amount_minor": 5000,
                    "policy_revision": POLICY_REVISION,
                    "policy_delivery": "provided",
                    "overlap": {"team_id": f["teams"][0], "confirmed": True},
                }
                # Use the application request contract, including explicit overlap flag.
                first = await api.post(
                    "/api/v1/staff/calendar-bookings",
                    headers=h("employee", 1),
                    json={k: v for k, v in payload.items() if k != "overlap"},
                )
                p.check(
                    "employee creates appointment",
                    first.status_code == 201,
                    http_status=first.status_code,
                )
                if first.status_code == 201:
                    original = (
                        await api.get(
                            "/api/v1/staff/jobs/" + first.json()["job_id"], headers=h("employee", 1)
                        )
                    ).json()
                    key = str(uuid.uuid4())
                    second = await api.post(
                        "/api/v1/staff/calendar-bookings",
                        headers=h("employee", 1, key),
                        json=payload,
                    )
                    p.check(
                        "employee intentional double booking",
                        second.status_code == 201,
                        http_status=second.status_code,
                    )
                    retry = await api.post(
                        "/api/v1/staff/calendar-bookings",
                        headers=h("employee", 1, key),
                        json=payload,
                    )
                    p.check(
                        "employee booking idempotency",
                        retry.status_code == 201 and retry.json() == second.json(),
                        http_status=retry.status_code,
                    )
                    unchanged = (
                        await api.get(
                            "/api/v1/staff/jobs/" + first.json()["job_id"], headers=h("employee", 1)
                        )
                    ).json()
                    p.check("double booking preserves original", unchanged == original)
                    foreign = await api.get(
                        "/api/v1/staff/jobs/" + first.json()["job_id"], headers=h("foreign_manager")
                    )
                    p.check(
                        "cross tenant job access denied",
                        foreign.status_code == 404,
                        http_status=foreign.status_code,
                    )
                for actor, status in [("customer_a", 403), ("other_employee", 404)]:
                    r = await api.post(
                        "/api/v1/staff/calendar-bookings", headers=h(actor, 1), json=payload
                    )
                    p.check(
                        "unauthorized double booking " + actor,
                        r.status_code == status,
                        http_status=r.status_code,
                    )
                # Real provider JWT plus payload tampering; do not execute charges.
                r = await api.post(
                    "/api/v1/public/holds",
                    json={
                        "date": await unused_date(50),
                        "start_time": "09:00",
                        "vehicle_count": 1,
                        "service_ids": [f["service"]],
                    },
                )
                p.check(
                    "customer availability hold", r.status_code == 201, http_status=r.status_code
                )
                if r.status_code == 201:
                    booking = {
                        k: v for k, v in payload.items() if k in ("contact", "location", "vehicles")
                    }
                    booking["location"] = {
                        **booking["location"],
                        "location_url": "https://maps.google.com/?q=Dubai",
                    }
                    booking.update(
                        hold_token=r.json()["hold_token"],
                        payment_choice="pay_after_service",
                        policy_acceptance={
                            "accepted": True,
                            "language": "en",
                            "revision": POLICY_REVISION,
                        },
                    )
                    booking["contact"] = {
                        **booking["contact"],
                        "email": "customer_a@security.example.com",
                    }
                    r = await api.post(
                        "/api/v1/public/bookings",
                        headers=h("customer_a", 1),
                        json={**booking, "total_amount_minor": 0, "payment_status": "paid"},
                    )
                    p.check(
                        "price and payment mass assignment denied",
                        r.status_code == 422,
                        http_status=r.status_code,
                    )
                    r = await api.post(
                        "/api/v1/public/bookings", headers=h("customer_a", 1), json=booking
                    )
                    p.check(
                        "customer booking server price",
                        r.status_code == 201 and r.json().get("total_amount_minor") == 5000,
                        http_status=r.status_code,
                    )
                    if r.status_code == 201:
                        bid = r.json()["id"]
                        p.config["customer_booking"] = bid
                        own = await api.get(
                            "/api/v1/customer/bookings/" + bid, headers=h("customer_a", 1)
                        )
                        p.check(
                            "own booking access",
                            own.status_code == 200,
                            http_status=own.status_code,
                        )
                        other = await api.get(
                            "/api/v1/customer/bookings/" + bid, headers=h("customer_b", 1)
                        )
                        p.check(
                            "booking IDOR denied",
                            other.status_code == 404,
                            http_status=other.status_code,
                        )
                for actor in ("customer_a", "customer_b"):
                    token = p.config["aal1_sessions"][actor]["access_token"]
                    for table in (
                        "customer_profiles",
                        "customer_addresses",
                        "bookings",
                        "payments",
                        "staff_profiles",
                    ):
                        r = await p.client.get(
                            p.config["url"] + "/rest/v1/" + table,
                            headers={
                                "apikey": p.config["publishable_key"],
                                "Authorization": "Bearer " + token,
                            },
                            params={"select": "*", "limit": 1},
                        )
                        p.check(
                            "native Data API denies " + actor + " " + table,
                            r.status_code == 403,
                            http_status=r.status_code,
                        )
                async with app.state.session_factory() as db:
                    roles = (
                        (
                            await db.execute(
                                text(
                                    "select current_user, (select rolbypassrls from pg_roles where rolname=current_user) bypass, (select count(*) from pg_tables where schemaname='public' and tableowner=current_user) owned"
                                )
                            )
                        )
                        .mappings()
                        .one()
                    )
                    p.check(
                        "real non-owner NOBYPASSRLS runtime",
                        roles["current_user"] == "trifecta_staging_api"
                        and not roles["bypass"]
                        and roles["owned"] == 0,
                    )
                    for sql, label in [
                        ("SET ROLE postgres", "runtime cannot assume owner"),
                        ("SELECT * FROM auth.users LIMIT 1", "runtime cannot read Auth users"),
                        (
                            "SELECT * FROM public.alembic_version",
                            "runtime cannot read migration state",
                        ),
                    ]:
                        try:
                            async with db.begin_nested():
                                await db.execute(text(sql))
                            p.check(label, False)
                        except DBAPIError as e:
                            p.check(label, getattr(e.orig, "sqlstate", None) == "42501")
                p.save()
    finally:
        p.save()
        await p.client.aclose()
    p.require_success()


if __name__ == "__main__":
    asyncio.run(main())

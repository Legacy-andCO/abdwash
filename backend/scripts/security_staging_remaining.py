"""Remaining non-destructive API integrations with current synthetic sessions."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import text

from security_staging_api import configure
from security_staging_probe import ROOT, Probe


async def main():
    configure()
    from app.main import app
    from app.services.policy_acceptance import POLICY_REVISION
    from app.workers.notifications import claim_batch, process_record

    p = Probe(ROOT / "docs/security-audit/follow-up/staging-remaining.json")
    try:
        # These are session preparation, not a repetition of the enrollment drill.
        for actor in ("customer_a", "customer_b", "employee", "manager", "foreign_manager"):
            login = await p.login(actor)
            p.config["aal1_sessions"][actor] = login
            if actor in ("manager", "foreign_manager"):
                factor = p.config["factors"][actor]
                response, _ = await p.verify(login["access_token"], factor["id"], factor["secret"])
                if response.status_code != 200:
                    raise RuntimeError("Native session preparation failed")
                p.config["aal2_sessions"][actor] = response.json()
        p.save()
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="https://staging-api.example.com"
            ) as api:

                def headers(actor, key=None):
                    sessions = (
                        p.config["aal2_sessions"]
                        if actor in ("manager", "foreign_manager")
                        else p.config["aal1_sessions"]
                    )
                    return {
                        "Authorization": "Bearer " + sessions[actor]["access_token"],
                        "Idempotency-Key": key or str(uuid.uuid4()),
                    }

                # Use the existing synthetic customer booking; no fixtures are deleted.
                bid = p.config["customer_booking"]
                path = f"/api/v1/customer/bookings/{bid}/cancellation-requests"
                denied = await api.post(
                    path,
                    headers=headers("customer_b"),
                    json={"reason": "Synthetic unauthorized cancellation"},
                )
                p.check(
                    "another customer cannot cancel booking",
                    denied.status_code == 404,
                    http_status=denied.status_code,
                )
                key = str(uuid.uuid4())
                one = await api.post(
                    path,
                    headers=headers("customer_a", key),
                    json={"reason": "Synthetic permitted cancellation"},
                )
                two = await api.post(
                    path,
                    headers=headers("customer_a", key),
                    json={"reason": "Synthetic permitted cancellation"},
                )
                p.check(
                    "owned booking cancellation works",
                    one.status_code == 201,
                    http_status=one.status_code,
                )
                p.check(
                    "cancellation retry is idempotent",
                    one.status_code == 201 and two.status_code == 201 and one.json() == two.json(),
                )
                complaint = {
                    "name": "Synthetic complaint",
                    "email": "complaint@security.example.com",
                    "category": "booking",
                    "description": "Synthetic staging security integration complaint.",
                    "privacy_acknowledged": True,
                    "revision": POLICY_REVISION,
                    "language": "en",
                }
                key = str(uuid.uuid4())
                created = await api.post(
                    "/api/v1/public/complaints", headers={"Idempotency-Key": key}, json=complaint
                )
                p.check(
                    "complaint creation without attachments",
                    created.status_code == 201,
                    http_status=created.status_code,
                )
                retried = await api.post(
                    "/api/v1/public/complaints", headers={"Idempotency-Key": key}, json=complaint
                )
                p.check(
                    "complaint idempotency",
                    retried.status_code == 201 and retried.json() == created.json(),
                )
                if created.status_code == 201:
                    ref = created.json()["reference"]
                    for actor, expected in (
                        ("customer_a", 403),
                        ("employee", 403),
                        ("foreign_manager", 404),
                        ("manager", 200),
                    ):
                        result = await api.get(
                            "/api/v1/staff/complaints/" + ref, headers=headers(actor)
                        )
                        p.check(
                            "complaint authorization " + actor,
                            result.status_code == expected,
                            http_status=result.status_code,
                        )
                statuses = []
                for _ in range(5):
                    result = await api.post(
                        "/api/v1/public/complaints",
                        headers={"Idempotency-Key": str(uuid.uuid4())},
                        json=complaint,
                    )
                    statuses.append(result.status_code)
                p.check(
                    "bounded complaint abuse reaches rate limit",
                    statuses[-1] == 429,
                    observed=statuses,
                )
                for query in ("-1", "10000000", "' OR '1'='1"):
                    result = await api.get(
                        "/api/v1/staff/complaints",
                        headers=headers("manager"),
                        params={"limit": query},
                    )
                    p.check(
                        "unsafe/unbounded API parameter rejected " + query,
                        result.status_code == 422,
                        http_status=result.status_code,
                    )
                # Three holds race for two teams on an unused day. No booking,
                # payment or original appointment is displaced by this test.
                for offset in range(80, 445):
                    day = (datetime.now(UTC) + timedelta(days=offset)).date()
                    async with app.state.session_factory() as db:
                        used = await db.scalar(
                            text(
                                "SELECT EXISTS(SELECT FROM slot_hold_groups WHERE slot_start::date=:day) OR EXISTS(SELECT FROM bookings WHERE scheduled_start::date=:day)"
                            ),
                            {"day": day},
                        )
                    if not used:
                        break
                else:
                    raise RuntimeError("No unused test date; nothing was reset")
                payload = {
                    "date": day.isoformat(),
                    "start_time": "09:00",
                    "vehicle_count": 1,
                    "service_ids": [p.config["fixtures"]["service"]],
                }
                results = await asyncio.gather(
                    *(api.post("/api/v1/public/holds", json=payload) for _ in range(3))
                )
                codes = [result.status_code for result in results]
                p.check(
                    "concurrent holds respect two-team capacity",
                    codes.count(201) == 2 and codes.count(409) == 1,
                    observed=codes,
                )
                p.check(
                    "staging notification delivery is log-only",
                    type(app.state.notification_provider).__name__ == "LogNotificationProvider",
                )
                worker = "security-audit-" + uuid.uuid4().hex
                ids = await claim_batch(app.state.session_factory, worker_id=worker, batch_size=10)
                states = [
                    await process_record(
                        app.state.session_factory,
                        app.state.notification_provider,
                        record_id,
                        worker_id=worker,
                        public_web_url="https://staging-web.example.com",
                    )
                    for record_id in ids
                ]
                p.check(
                    "synthetic notification worker processes safely",
                    bool(states) and all(state in ("sent", "skipped") for state in states),
                    outcomes=states,
                )
    finally:
        p.save()
        await p.client.aclose()
    p.require_success()


if __name__ == "__main__":
    asyncio.run(main())

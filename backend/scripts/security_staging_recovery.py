"""Rehearse operator-assisted recovery with synthetic identities only.

Native Admin operations run through the expiring staging operator. Company
identity verification and independent human approval remain a manual drill;
the synthetic approver identities here test technical sequencing only.
"""

import asyncio
import time
import uuid

import httpx
import jwt
from sqlalchemy import text

import security_staging_probe as s
from security_staging_api import configure


async def main():
    configure()
    from app.main import app

    p = s.Probe(s.ROOT / "docs/security-audit/follow-up/staging-recovery.json")
    case = str(uuid.uuid4())
    f = p.config["fixtures"]
    try:
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="https://staging-api.example.com"
            ) as api:

                def hdr(token):
                    return {
                        "Authorization": "Bearer " + token,
                        "Idempotency-Key": str(uuid.uuid4()),
                    }

                async def context(token):
                    return await api.get("/api/v1/staff/context", headers=hdr(token))

                old = p.config["aal2_sessions"]["manager"]["access_token"]
                claims = jwt.decode(old, options={"verify_signature": False})
                timestamp = max(x["timestamp"] for x in claims["amr"] if x["method"] == "totp")
                if time.time() - timestamp > 300:
                    r = await api.post(
                        "/api/v1/staff/bookings/"
                        + p.config["customer_booking"]
                        + "/guest-access/revoke",
                        headers=hdr(old),
                    )
                    p.check(
                        "real aged TOTP denies privileged mutation",
                        r.status_code == 403
                        and r.json().get("detail", {}).get("code")
                        == "MFA_REAUTHENTICATION_REQUIRED",
                        http_status=r.status_code,
                    )
                else:
                    p.results.append(
                        {
                            "test": "real aged TOTP denies privileged mutation",
                            "status": "NOT TESTED",
                            "reason": "native AMR not five minutes old",
                        }
                    )
                employee = p.config["aal1_sessions"]["employee"]["access_token"]
                edit = await p.auth(
                    "PUT", "/user", employee, json={"data": {"role": "admin", "aal": "aal2"}}
                )
                r = await context(employee)
                p.check(
                    "user-editable metadata cannot promote staff",
                    edit.status_code == 200
                    and r.status_code == 200
                    and r.json()["role"] == "employee",
                    http_status=r.status_code,
                )
                attempt = await p.client.post(
                    p.config["url"] + "/functions/v1/security-staging-operator",
                    headers=hdr(p.config["aal1_sessions"]["customer_a"]["access_token"]),
                    json={
                        "op": "delete_factor",
                        "user_id": p.config["users"]["manager"],
                        "factor_id": p.config["factors"]["manager"]["id"],
                    },
                )
                p.check(
                    "customer JWT cannot invoke operator recovery",
                    attempt.status_code == 401,
                    http_status=attempt.status_code,
                )
                approvers = []
                for name in ["admin", "admin_two"]:
                    login = await p.login(name)
                    factor = p.config["factors"][name]
                    verified, _ = await p.verify(
                        login["access_token"], factor["id"], factor["secret"]
                    )
                    p.check(
                        "native fresh recovery approver MFA " + name,
                        verified.status_code == 200,
                        http_status=verified.status_code,
                    )
                    if verified.status_code != 200:
                        raise RuntimeError("Recovery approver failed MFA")
                    p.config["aal2_sessions"][name] = verified.json()
                    r = await context(verified.json()["access_token"])
                    p.check(
                        "recovery approver is authoritative admin " + name,
                        r.status_code == 200 and r.json()["role"] == "admin",
                        http_status=r.status_code,
                    )
                    approvers.append(p.config["users"][name])
                p.check("recovery approvers are distinct", len(set(approvers)) == 2)

                async def audit(event):
                    import json

                    async with app.state.session_factory() as db, db.begin():
                        await db.execute(
                            text(
                                "INSERT INTO audit_events(id,business_id,actor_auth_user_id,event_type,entity_type,entity_id,metadata) VALUES (:id,:b,:actor,:event,'staff_profile',:target,CAST(:meta AS json))"
                            ),
                            {
                                "id": uuid.uuid4(),
                                "b": uuid.UUID(f["businesses"][0]),
                                "actor": uuid.UUID(approvers[0]),
                                "event": event,
                                "target": uuid.UUID(f["staff"]["manager"]),
                                "meta": json.dumps(
                                    {
                                        "case": case,
                                        "approvers": approvers,
                                        "synthetic_drill": True,
                                        "identity_verification": "simulated company-record check; human process not certified",
                                    }
                                ),
                            },
                        )

                async with app.state.session_factory() as db, db.begin():
                    await db.execute(
                        text("UPDATE staff_profiles SET is_active=false WHERE id=:id"),
                        {"id": uuid.UUID(f["staff"]["manager"])},
                    )
                await audit("mfa_recovery_started")
                r = await context(old)
                p.check(
                    "recovery suspends staff before factor removal",
                    r.status_code == 403,
                    http_status=r.status_code,
                )
                await p.operator("sign_out", user_id=p.config["users"]["manager"], access_token=old)
                await p.operator("ban", user_id=p.config["users"]["manager"])
                r = await context(old)
                p.check(
                    "stolen old aal2 token denied after global signout",
                    r.status_code == 401,
                    http_status=r.status_code,
                )
                refresh = await p.auth(
                    "POST",
                    "/token?grant_type=refresh_token",
                    json={"refresh_token": p.config["aal2_sessions"]["manager"]["refresh_token"]},
                )
                p.check(
                    "revoked refresh token cannot replay",
                    refresh.status_code == 400,
                    http_status=refresh.status_code,
                    error_code=refresh.json().get("code"),
                )
                oldfactor = p.config["factors"]["manager"]["id"]
                await p.operator(
                    "delete_factor", user_id=p.config["users"]["manager"], factor_id=oldfactor
                )
                await audit("mfa_recovery_factor_removed")
                await p.operator("unban", user_id=p.config["users"]["manager"])
                login = await p.login("manager")
                token = login["access_token"]
                p.config["aal1_sessions"]["manager"] = login
                r = await context(token)
                p.check(
                    "password-only recovery never grants manager access",
                    r.status_code == 403,
                    http_status=r.status_code,
                )
                enrolled = await p.auth(
                    "POST",
                    "/factors",
                    token,
                    json={"factor_type": "totp", "friendly_name": "Recovered staging " + case[:8]},
                )
                p.check(
                    "recovery enrolls new native factor",
                    enrolled.status_code == 200,
                    http_status=enrolled.status_code,
                )
                if enrolled.status_code != 200:
                    raise RuntimeError("Recovered enrollment failed; staff remains suspended")
                factor = enrolled.json()
                secret = factor["totp"]["secret"]
                verified, _ = await p.verify(token, factor["id"], secret)
                p.check(
                    "recovery verifies new native TOTP",
                    verified.status_code == 200,
                    http_status=verified.status_code,
                )
                if verified.status_code != 200:
                    raise RuntimeError("Recovered factor failed; staff remains suspended")
                newtoken = verified.json()["access_token"]
                p.config["factors"]["manager"] = {"id": factor["id"], "secret": secret}
                p.config["aal2_sessions"]["manager"] = verified.json()
                p.save()
                r = await context(newtoken)
                p.check(
                    "verified factor alone cannot bypass recovery suspension",
                    r.status_code == 403,
                    http_status=r.status_code,
                )
                async with app.state.session_factory() as db, db.begin():
                    await db.execute(
                        text("UPDATE staff_profiles SET is_active=true WHERE id=:id"),
                        {"id": uuid.UUID(f["staff"]["manager"])},
                    )
                await audit("mfa_recovery_completed")
                r = await context(newtoken)
                p.check(
                    "recovered manager resumes only with aal2",
                    r.status_code == 200,
                    http_status=r.status_code,
                )
                r = await api.post(
                    "/api/v1/staff/bookings/"
                    + p.config["customer_booking"]
                    + "/guest-access/revoke",
                    headers=hdr(newtoken),
                )
                p.check(
                    "fresh native MFA privileged mutation works",
                    r.status_code == 204,
                    http_status=r.status_code,
                )
                async with app.state.session_factory() as db:
                    count = await db.scalar(
                        text("SELECT count(*) FROM audit_events WHERE metadata->>'case'=:case"),
                        {"case": case},
                    )
                p.check("recovery audit sequence recorded", count == 3, audit_events=count)
                # Exercise native authorized removal against an otherwise live session.
                native_delete = await p.auth("DELETE", "/factors/" + factor["id"], newtoken)
                p.check(
                    "native aal2 factor removal allowed",
                    native_delete.status_code == 200,
                    http_status=native_delete.status_code,
                )
                r = await context(newtoken)
                p.check(
                    "unchanged old aal2 JWT cannot outlive factor removal",
                    r.status_code in (401, 403),
                    http_status=r.status_code,
                )
                # Re-enroll immediately; do not leave the synthetic manager exempt.
                login = await p.login("manager")
                token = login["access_token"]
                enrolled = await p.auth(
                    "POST",
                    "/factors",
                    token,
                    json={"factor_type": "totp", "friendly_name": "Final staging manager"},
                )
                if enrolled.status_code != 200:
                    raise RuntimeError("Final enrollment failed")
                factor = enrolled.json()
                verified, _ = await p.verify(token, factor["id"], factor["totp"]["secret"])
                p.check(
                    "synthetic manager restored with mandatory MFA",
                    verified.status_code == 200,
                    http_status=verified.status_code,
                )
                if verified.status_code == 200:
                    p.config["factors"]["manager"] = {
                        "id": factor["id"],
                        "secret": factor["totp"]["secret"],
                    }
                    p.config["aal1_sessions"]["manager"] = login
                    p.config["aal2_sessions"]["manager"] = verified.json()
    finally:
        p.save()
        await p.client.aclose()
    p.require_success()


if __name__ == "__main__":
    asyncio.run(main())

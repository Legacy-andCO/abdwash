"""Read-only/denied-request authentication regressions after final code review."""

import asyncio
import base64
import json
import time

import httpx
import jwt

from security_staging_api import configure
from security_staging_probe import ROOT, Probe


async def main():
    configure()
    from app.main import app

    p = Probe(ROOT / "docs/security-audit/follow-up/staging-auth-regression.json")
    try:
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="https://staging-api.example.com"
            ) as api:
                expired = next(
                    (
                        session["access_token"]
                        for session in p.config["aal2_sessions"].values()
                        if jwt.decode(session["access_token"], options={"verify_signature": False})[
                            "exp"
                        ]
                        < time.time()
                    ),
                    None,
                )
                if expired:
                    try:
                        await app.state.auth_verifier.verify(expired)
                        expired_cause = "accepted"
                    except Exception as exc:
                        expired_cause = type(exc.__cause__).__name__
                    result = await api.get(
                        "/api/v1/staff/context", headers={"Authorization": "Bearer " + expired}
                    )
                    p.check(
                        "real expired native JWT rejected without expiry grace",
                        expired_cause == "ExpiredSignatureError" and result.status_code == 401,
                        http_status=result.status_code,
                        verifier_reason=expired_cause,
                    )
                else:
                    p.results.append(
                        {
                            "test": "real expired native JWT rejected without expiry grace",
                            "status": "NOT TESTED",
                            "reason": "No stored native token has naturally expired",
                        }
                    )
                original = p.config["aal1_sessions"]["employee"]["access_token"]
                header, _, signature = original.split(".")
                claims = jwt.decode(original, options={"verify_signature": False})
                claims.update(
                    aal="aal2", role="admin", amr=[{"method": "totp", "timestamp": time.time()}]
                )
                payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
                result = await api.get(
                    "/api/v1/staff/context",
                    headers={"Authorization": f"Bearer {header}.{payload}.{signature}"},
                )
                p.check(
                    "forged privileged assurance cannot reuse native signature",
                    result.status_code == 401,
                    http_status=result.status_code,
                )
                token = p.config["aal2_sessions"]["manager"]["access_token"]
                claims = jwt.decode(token, options={"verify_signature": False})
                stamp = max(x["timestamp"] for x in claims["amr"] if x["method"] == "totp")
                if 300 < time.time() - stamp < 86400 and claims["exp"] > time.time():
                    result = await api.patch(
                        "/api/v1/staff/profile",
                        headers={"Authorization": "Bearer " + token},
                        json={"display_name": "Synthetic manager"},
                    )
                    p.check(
                        "naturally aged native TOTP blocks privileged mutation",
                        result.status_code == 403
                        and result.json().get("detail", {}).get("code")
                        == "MFA_REAUTHENTICATION_REQUIRED",
                        http_status=result.status_code,
                    )
                else:
                    p.results.append(
                        {
                            "test": "naturally aged native TOTP blocks privileged mutation",
                            "status": "NOT TESTED",
                            "reason": "Stored native session is not in the required age/expiry window",
                        }
                    )
    finally:
        p.save()
        await p.client.aclose()
    p.require_success()


if __name__ == "__main__":
    asyncio.run(main())

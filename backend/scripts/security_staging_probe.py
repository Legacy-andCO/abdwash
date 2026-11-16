"""Opt-in real-provider probe, hard-pinned to the isolated synthetic project.

Secrets stay in ignored tmp/security-staging.json; evidence contains outcomes
only. Never points to DATABASE_URL, never resets schemas or copies live data.
"""

import asyncio
import base64
import hashlib
import hmac
import io
import json
import logging
import struct
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
import jwt
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "tmp/security-staging.json"
EVIDENCE = ROOT / "docs/security-audit/follow-up/staging-native.json"
logging.getLogger("httpx").setLevel(logging.WARNING)


def totp(secret: str, offset: int = 0) -> str:
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    digest = hmac.new(
        key, struct.pack(">Q", int(time.time() + offset) // 30), hashlib.sha1
    ).digest()
    start = digest[-1] & 15
    return f"{(struct.unpack('>I', digest[start : start + 4])[0] & 0x7FFFFFFF) % 1000000:06d}"


class Probe:
    def __init__(self, evidence=None):
        self.evidence = evidence or ROOT / "tmp/staging-probe-scratch.json"
        self.config = json.loads(CONFIG.read_text())
        if (
            self.config["project_ref"] != "mgfzfgvlrxwyyftwukwf"
            or self.config["url"] != "https://mgfzfgvlrxwyyftwukwf.supabase.co"
        ):
            raise RuntimeError("Only the isolated synthetic staging project is permitted")
        self.results = []
        self.client = httpx.AsyncClient(timeout=40)

    def save(self):
        CONFIG.write_text(json.dumps(self.config), encoding="utf-8")
        self.evidence.write_text(
            json.dumps(
                {
                    "project_ref": self.config["project_ref"],
                    "executed_at": datetime.now(UTC).isoformat(),
                    "tests": self.results,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def check(self, name, condition, **detail):
        self.results.append({"test": name, "status": "PASS" if condition else "FAIL", **detail})
        print(self.results[-1], flush=True)
        self.save()

    def require_success(self):
        failures = sum(row["status"] == "FAIL" for row in self.results)
        if failures:
            raise RuntimeError(f"{failures} security assertions failed; inspect the evidence file")

    async def auth(self, method, path, token=None, **kwargs):
        headers = {"apikey": self.config["publishable_key"]}
        if token:
            headers["Authorization"] = "Bearer " + token
        return await self.client.request(
            method, self.config["url"] + "/auth/v1" + path, headers=headers, **kwargs
        )

    async def operator(self, op, **kwargs):
        r = await self.client.post(
            self.config["url"] + "/functions/v1/security-staging-operator",
            headers={"x-staging-operator": self.config["operator_token"]},
            json={"op": op, **kwargs},
        )
        if r.status_code != 200:
            raise RuntimeError(f"Operator {op} failed: HTTP {r.status_code}")
        return r.json()

    async def login(self, name):
        r = await self.auth(
            "POST",
            "/token?grant_type=password",
            json={
                "email": name + "@" + self.config.get("email_domain", "security.trifecta.invalid"),
                "password": self.config["passwords"][name],
            },
        )
        self.check("native password login " + name, r.status_code == 200, http_status=r.status_code)
        if r.status_code != 200:
            raise RuntimeError("Native login failed")
        return r.json()

    async def verify(self, token, factor, secret, offset=0):
        c = await self.auth("POST", f"/factors/{factor}/challenge", token, json={})
        if c.status_code != 200:
            raise RuntimeError(f"Native challenge failed: {c.status_code}")
        challenge = c.json()["id"]
        r = await self.auth(
            "POST",
            f"/factors/{factor}/verify",
            token,
            json={"challenge_id": challenge, "code": totp(secret, offset)},
        )
        return r, challenge

    async def native(self):
        sessions = {}
        for name in self.config["users"]:
            sessions[name] = await self.login(name)
        self.config["aal1_sessions"] = sessions
        self.config.setdefault("factors", {})
        self.config.setdefault("aal2_sessions", {})
        for name in ("manager", "admin", "admin_two", "foreign_manager"):
            token = sessions[name]["access_token"]
            r = await self.auth(
                "POST",
                "/factors",
                token,
                json={
                    "factor_type": "totp",
                    "friendly_name": "Security audit " + str(uuid.uuid4())[:8],
                    "issuer": "Trifecta staging",
                },
            )
            self.check(
                "native TOTP enrollment " + name, r.status_code == 200, http_status=r.status_code
            )
            if r.status_code != 200:
                raise RuntimeError("Enrollment failed")
            data = r.json()
            factor = data["id"]
            secret = data["totp"]["secret"]
            qr = data["totp"]["qr_code"]
            self.check(
                "native private QR returned " + name,
                "svg" in qr.lower() or qr.startswith("data:image/"),
            )
            self.config["factors"][name] = {"id": factor, "secret": secret}
            self.save()
            if name == "manager":
                bad, _ = await self.verify(token, factor, secret, -300)
                self.check(
                    "expired TOTP cannot verify",
                    bad.status_code in (400, 422),
                    http_status=bad.status_code,
                    error_code=bad.json().get("code"),
                )
            good, challenge = await self.verify(token, factor, secret)
            self.check(
                "native correct TOTP verification " + name,
                good.status_code == 200,
                http_status=good.status_code,
            )
            if good.status_code != 200:
                raise RuntimeError("Native verification failed")
            self.config["aal2_sessions"][name] = good.json()
            self.save()
            claims = jwt.decode(good.json()["access_token"], options={"verify_signature": False})
            self.check(
                "provider issued aal2 and totp AMR " + name,
                claims.get("aal") == "aal2"
                and any(x.get("method") == "totp" for x in claims.get("amr", [])),
            )
            if name == "manager":
                replay = await self.auth(
                    "POST",
                    f"/factors/{factor}/verify",
                    token,
                    json={"challenge_id": challenge, "code": totp(secret)},
                )
                self.check(
                    "used MFA challenge cannot replay",
                    replay.status_code in (400, 422),
                    http_status=replay.status_code,
                    error_code=replay.json().get("code"),
                )
                fresh = await self.login(name)
                self.config["aal1_sessions"][name] = fresh
                fresh_token = fresh["access_token"]
                self.check(
                    "subsequent password login is aal1",
                    jwt.decode(fresh_token, options={"verify_signature": False}).get("aal")
                    == "aal1",
                )
                removal = await self.auth("DELETE", f"/factors/{factor}", fresh_token)
                self.check(
                    "stolen aal1 cannot remove verified factor",
                    removal.status_code in (400, 403, 422),
                    http_status=removal.status_code,
                    error_code=removal.json().get("code"),
                )
                extra = await self.auth(
                    "POST",
                    "/factors",
                    fresh_token,
                    json={"factor_type": "totp", "friendly_name": "AAL1 bypass probe"},
                )
                self.check(
                    "stolen aal1 cannot enroll replacement factor",
                    extra.status_code in (400, 403, 422),
                    http_status=extra.status_code,
                    error_code=extra.json().get("code"),
                )
                if extra.status_code == 200:
                    # Unverified synthetic probe only; no verified factor is removed.
                    await self.auth("DELETE", "/factors/" + extra.json()["id"], fresh_token)
        wrong = await self.auth(
            "POST",
            "/token?grant_type=password",
            json={
                "email": "manager@security.trifecta.invalid",
                "password": "incorrect-synthetic-password",
            },
        )
        self.check(
            "incorrect password rejected",
            wrong.status_code == 400,
            http_status=wrong.status_code,
            error_code=wrong.json().get("code"),
        )
        self.save()

    async def storage(self):
        buf = io.BytesIO()
        Image.new("RGB", (2, 2), (123, 234, 90)).save(buf, format="PNG")
        png = buf.getvalue()
        suffix = uuid.uuid4().hex
        for bucket in ("job-quality-photos", "complaint-evidence", "expense-evidence"):
            path = f"security-audit/customer_a/{suffix}.png"
            signed = await self.operator("upload", bucket=bucket, path=path)
            upload = await self.client.put(
                signed["signedUrl"],
                content=png,
                headers={"content-type": "image/png", "x-upsert": "false"},
            )
            self.check(
                "signed immutable upload " + bucket,
                upload.status_code == 200,
                http_status=upload.status_code,
            )
            repeat = await self.client.put(
                signed["signedUrl"],
                content=png,
                headers={"content-type": "image/png", "x-upsert": "true"},
            )
            self.check(
                "upload token cannot overwrite " + bucket,
                repeat.status_code in (400, 409),
                http_status=repeat.status_code,
            )
            for actor in (None, "customer_a", "customer_b"):
                headers = {"apikey": self.config["publishable_key"]}
                if actor:
                    headers["Authorization"] = (
                        "Bearer " + self.config["aal1_sessions"][actor]["access_token"]
                    )
                direct = await self.client.get(
                    self.config["url"] + f"/storage/v1/object/authenticated/{bucket}/{path}",
                    headers=headers,
                )
                self.check(
                    f"direct private read denied {bucket} {actor or 'anon'}",
                    direct.status_code in (400, 401, 403, 404),
                    http_status=direct.status_code,
                )
                listing = await self.client.post(
                    self.config["url"] + f"/storage/v1/object/list/{bucket}",
                    headers=headers,
                    json={"prefix": "security-audit/", "limit": 10},
                )
                self.check(
                    f"private listing empty/denied {bucket} {actor or 'anon'}",
                    listing.status_code in (400, 401, 403, 404)
                    or (listing.status_code == 200 and listing.json() == []),
                    http_status=listing.status_code,
                )
            download = await self.operator("download", bucket=bucket, path=path, seconds=2)
            good = await self.client.get(download["signedUrl"])
            self.check(
                "signed download works " + bucket,
                good.status_code == 200 and good.content == png,
                http_status=good.status_code,
            )
            tampered = await self.client.get(download["signedUrl"].replace(suffix, "other_object"))
            self.check(
                "signed download path tampering denied " + bucket,
                tampered.status_code in (400, 401, 403, 404),
                http_status=tampered.status_code,
            )
            await asyncio.sleep(4)
            expired = await self.client.get(download["signedUrl"])
            self.check(
                "signed download expired " + bucket,
                expired.status_code in (400, 401, 403, 404),
                http_status=expired.status_code,
            )
            badpath = f"security-audit/customer_a/{suffix}_bad.png"
            badsigned = await self.operator("upload", bucket=bucket, path=badpath)
            mime = await self.client.put(
                badsigned["signedUrl"],
                content=b"<svg onload=alert(1)>",
                headers={"content-type": "image/svg+xml"},
            )
            self.check(
                "active MIME upload denied " + bucket,
                mime.status_code in (400, 403, 413, 415),
                http_status=mime.status_code,
            )
        self.save()


async def main():
    p = Probe(EVIDENCE)
    try:
        await p.native()
        await p.storage()
    finally:
        p.save()
        await p.client.aclose()
    p.require_success()


if __name__ == "__main__":
    asyncio.run(main())

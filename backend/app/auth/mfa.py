"""Privileged assurance is taken only from verified JWTs and authoritative SQL roles."""

import time

from fastapi import HTTPException

from app.auth.verifier import ISSUANCE_CLOCK_SKEW_SECONDS, VerifiedIdentity


def require_privileged_totp(identity: VerifiedIdentity, *, sensitive: bool) -> None:
    claims = identity.claims
    methods = claims.get("amr", [])
    timestamps = (
        [m.get("timestamp") for m in methods if isinstance(m, dict) and m.get("method") == "totp"]
        if isinstance(methods, list)
        else []
    )
    valid = [
        t
        for t in timestamps
        if isinstance(t, (int, float))
        and not isinstance(t, bool)
        and -ISSUANCE_CLOCK_SKEW_SECONDS <= time.time() - t <= 86400
    ]
    if claims.get("aal") != "aal2" or not valid:
        raise HTTPException(403, detail={"code": "MFA_REQUIRED"})
    if sensitive and time.time() - max(valid) > 300:
        raise HTTPException(403, detail={"code": "MFA_REAUTHENTICATION_REQUIRED"})


def require_recent_password(identity: VerifiedIdentity) -> None:
    """Bound employee password changes to a recent native password sign-in."""
    methods = identity.claims.get("amr", [])
    if isinstance(methods, list):
        for method in methods:
            if not isinstance(method, dict) or method.get("method") != "password":
                continue
            timestamp = method.get("timestamp")
            if (
                isinstance(timestamp, (int, float))
                and not isinstance(timestamp, bool)
                and -ISSUANCE_CLOCK_SKEW_SECONDS <= time.time() - timestamp <= 300
            ):
                return
    raise HTTPException(403, detail={"code": "REAUTHENTICATION_REQUIRED"})

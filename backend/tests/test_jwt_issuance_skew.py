"""Provider issuance skew must not become a grace period for expired tokens."""

import time
import uuid

import httpx
import jwt
import pytest

from app.auth.verifier import AuthenticationError, SupabaseTokenVerifier
from app.core.config import Settings
from test_auth_verifier import signing_material


@pytest.mark.parametrize("algorithm", ["HS256", "RS256"])
@pytest.mark.parametrize(
    "offset,expired,allowed", [(2, False, True), (15, False, False), (0, True, False)]
)
async def test_bounded_issuance_skew_keeps_expiration_strict(algorithm, offset, expired, allowed):
    secret = "synthetic-only-issuance-test-key-" + "x" * 32
    private, jwk = signing_material("clock-test")
    now = time.time()
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "aud": "authenticated",
            "iss": "https://audit.supabase.co/auth/v1",
            "exp": now - 1 if expired else now + 60,
            "iat": now + offset,
        },
        secret if algorithm == "HS256" else private,
        algorithm=algorithm,
        headers={"kid": "clock-test"},
    )
    settings = Settings(
        _env_file=None,
        app_env="test",
        supabase_url="https://audit.supabase.co",
        supabase_jwt_secret=secret,
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"keys": [jwk]}))
    ) as client:
        verifier = SupabaseTokenVerifier(settings, client)
        if allowed:
            assert (await verifier.verify(token)).user_id
        else:
            with pytest.raises(AuthenticationError):
                await verifier.verify(token)


@pytest.mark.parametrize("issued_at", [None, True, "12", -1, float("nan"), float("inf")])
async def test_invalid_issuance_claim_is_rejected(issued_at):
    secret = "synthetic-invalid-issuance-key-" + "x" * 32
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "aud": "authenticated",
            "iss": "https://audit.supabase.co/auth/v1",
            "exp": time.time() + 60,
            "iat": issued_at,
        },
        secret,
        algorithm="HS256",
    )
    async with httpx.AsyncClient() as client:
        verifier = SupabaseTokenVerifier(
            Settings(
                _env_file=None,
                app_env="test",
                supabase_url="https://audit.supabase.co",
                supabase_jwt_secret=secret,
            ),
            client,
        )
        with pytest.raises(AuthenticationError):
            await verifier.verify(token)

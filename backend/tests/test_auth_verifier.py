import time
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jwt import PyJWKSet

import app.auth.verifier as verifier_module
from app.auth.dependencies import optional_identity
from app.auth.verifier import (
    AuthenticationServiceUnavailable,
    SupabaseTokenVerifier,
)
from app.core.config import Settings


def settings(**overrides: object) -> Settings:
    return Settings(
        app_env="test",
        booking_management_signing_key="x" * 48,
        supabase_url="https://project.supabase.co",
        jwks_cache_ttl_seconds=600,
        **overrides,
    )


def signing_material(key_id: str) -> tuple[object, dict[str, object]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(
        private_key.public_key(),
        as_dict=True,
    )
    public_jwk.update({"kid": key_id, "alg": "RS256", "use": "sig"})
    return private_key, public_jwk


def token_for(
    private_key: object,
    key_id: str,
    *,
    expires_at: datetime | None = None,
) -> tuple[str, uuid.UUID]:
    user_id = uuid.uuid4()
    encoded = jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "iss": "https://project.supabase.co/auth/v1",
            "exp": expires_at or datetime.now(UTC) + timedelta(hours=1),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": key_id},
    )
    return encoded, user_id


def jwks(*keys: dict[str, object]) -> PyJWKSet:
    return PyJWKSet.from_dict({"keys": list(keys)})


async def verify_request(
    verifier: SupabaseTokenVerifier,
    token: str,
) -> object:
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(auth_verifier=verifier)),
        state=SimpleNamespace(),
    )
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )
    return await optional_identity(request, credentials)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_fresh_jwks_loads_and_verifies_locally() -> None:
    private_key, public_jwk = signing_material("current-key")
    token, user_id = token_for(private_key, "current-key")
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json={"keys": [public_jwk]}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        verifier = SupabaseTokenVerifier(settings(), client)
        assert (await verifier.verify(token)).user_id == user_id
        assert (await verifier.verify(token)).user_id == user_id

    assert requests == 1


@pytest.mark.asyncio
async def test_expired_cache_refreshes_successfully() -> None:
    private_key, public_jwk = signing_material("current-key")
    token, user_id = token_for(private_key, "current-key")
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json={"keys": [public_jwk]}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        verifier = SupabaseTokenVerifier(settings(), client)
        verifier._jwks = jwks(public_jwk)
        verifier._jwks_loaded_at = time.monotonic() - 601
        assert (await verifier.verify(token)).user_id == user_id

    assert requests == 1
    assert verifier._jwks_loaded_at > time.monotonic() - 10


@pytest.mark.asyncio
async def test_expired_cache_timeout_uses_known_stale_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key, public_jwk = signing_material("current-key")
    token, user_id = token_for(private_key, "current-key")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("JWKS timed out", request=request)

    diagnostics = MagicMock()
    monkeypatch.setattr(verifier_module, "logger", diagnostics)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        verifier = SupabaseTokenVerifier(settings(), client)
        cached = jwks(public_jwk)
        verifier._jwks = cached
        verifier._jwks_loaded_at = time.monotonic() - 601
        assert (await verifier.verify(token)).user_id == user_id
        assert verifier._jwks is cached
    diagnostics.warning.assert_any_call("jwks_refresh_timeout")
    diagnostics.warning.assert_any_call("jwks_stale_fallback", reason="timeout")
    assert token not in str(diagnostics.mock_calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["network", "server_error"])
async def test_expired_cache_uses_known_key_for_other_transient_failures(
    failure: str,
) -> None:
    private_key, public_jwk = signing_material("current-key")
    token, user_id = token_for(private_key, "current-key")

    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "network":
            raise httpx.ConnectError("JWKS unavailable", request=request)
        return httpx.Response(503, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        verifier = SupabaseTokenVerifier(settings(), client)
        verifier._jwks = jwks(public_jwk)
        verifier._jwks_loaded_at = time.monotonic() - 601
        assert (await verifier.verify(token)).user_id == user_id


@pytest.mark.asyncio
async def test_unknown_kid_forces_refresh_even_with_fresh_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_private_key, old_public_jwk = signing_material("old-key")
    new_private_key, new_public_jwk = signing_material("rotated-key")
    del old_private_key
    token, user_id = token_for(new_private_key, "rotated-key")
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json={"keys": [new_public_jwk]}, request=request)

    diagnostics = MagicMock()
    monkeypatch.setattr(verifier_module, "logger", diagnostics)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        verifier = SupabaseTokenVerifier(settings(), client)
        verifier._jwks = jwks(old_public_jwk)
        verifier._jwks_loaded_at = time.monotonic()
        assert (await verifier.verify(token)).user_id == user_id

    assert requests == 1
    diagnostics.info.assert_any_call("unknown_kid")
    diagnostics.info.assert_any_call("jwks_refresh_success", key_count=1)
    assert token not in str(diagnostics.mock_calls)


@pytest.mark.asyncio
async def test_no_cache_provider_outage_is_service_unavailable() -> None:
    private_key, _public_jwk = signing_material("current-key")
    token, _user_id = token_for(private_key, "current-key")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("JWKS unavailable", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        verifier = SupabaseTokenVerifier(settings(), client)
        with pytest.raises(AuthenticationServiceUnavailable):
            await verifier.verify(token)


@pytest.mark.asyncio
async def test_expired_token_remains_invalid_with_fresh_cached_key() -> None:
    private_key, public_jwk = signing_material("current-key")
    token, _user_id = token_for(
        private_key,
        "current-key",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    async with httpx.AsyncClient() as client:
        verifier = SupabaseTokenVerifier(settings(), client)
        verifier._jwks = jwks(public_jwk)
        verifier._jwks_loaded_at = time.monotonic()
        with pytest.raises(HTTPException) as error:
            await verify_request(verifier, token)
    assert error.value.status_code == 401
    assert error.value.detail == {"code": "INVALID_TOKEN"}


@pytest.mark.asyncio
async def test_invalid_signature_remains_invalid_with_fresh_cached_key() -> None:
    expected_private_key, expected_public_jwk = signing_material("current-key")
    attacker_private_key, _attacker_public_jwk = signing_material("attacker-key")
    del expected_private_key
    token, _user_id = token_for(attacker_private_key, "current-key")
    async with httpx.AsyncClient() as client:
        verifier = SupabaseTokenVerifier(settings(), client)
        verifier._jwks = jwks(expected_public_jwk)
        verifier._jwks_loaded_at = time.monotonic()
        with pytest.raises(HTTPException) as error:
            await verify_request(verifier, token)
    assert error.value.status_code == 401
    assert error.value.detail == {"code": "INVALID_TOKEN"}


@pytest.mark.asyncio
async def test_hs256_verification_behavior_is_preserved() -> None:
    legacy_key = str(uuid.uuid4())
    legacy_settings = settings(supabase_jwt_secret=legacy_key)
    user_id = uuid.uuid4()
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "iss": "https://project.supabase.co/auth/v1",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        legacy_key,
        algorithm="HS256",
    )
    async with httpx.AsyncClient() as client:
        verifier = SupabaseTokenVerifier(legacy_settings, client)
        assert (await verifier.verify(token)).user_id == user_id


@pytest.mark.asyncio
async def test_auth_dependency_maps_provider_outage_to_503() -> None:
    verifier = SimpleNamespace(
        verify=AsyncMock(
            side_effect=AuthenticationServiceUnavailable("provider unavailable")
        )
    )
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(auth_verifier=verifier)),
        state=SimpleNamespace(),
    )
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="sanitized-test-token",
    )

    with pytest.raises(HTTPException) as error:
        await optional_identity(request, credentials)  # type: ignore[arg-type]

    assert error.value.status_code == 503
    assert error.value.detail == {"code": "AUTHENTICATION_SERVICE_UNAVAILABLE"}

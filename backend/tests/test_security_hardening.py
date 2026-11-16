"""Synthetic exploit regressions; no external services or production data."""

import base64
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import jwt
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.auth.dependencies import required_identity, staff_context
from app.auth.verifier import AuthenticationError, SupabaseTokenVerifier, VerifiedIdentity
from app.core.config import Settings
from app.core.database import session_dependency
from app.domain.errors import DomainError
from app.integrations.supabase_storage import SupabaseStorageAdminClient
from app.services.image_validation import validate_image


def audit_settings(**values: object) -> Settings:
    return Settings(
        _env_file=None, app_env="test", supabase_url="https://audit.supabase.co", **values
    )


@pytest.mark.parametrize("algorithm", [[], {}])
async def test_malformed_jwt_algorithm_is_rejected_without_an_internal_error(algorithm):
    header = base64.urlsafe_b64encode(json.dumps({"alg": algorithm}).encode()).decode().rstrip("=")
    async with httpx.AsyncClient() as client:
        verifier = SupabaseTokenVerifier(audit_settings(), client)
        with pytest.raises(AuthenticationError):
            await verifier.verify(f"{header}.e30.eA")


@pytest.mark.parametrize("missing", ["exp", "iss", "aud", "sub"])
async def test_signed_access_token_requires_security_claims(missing: str) -> None:
    claims = {
        "sub": str(uuid.uuid4()),
        "aud": "authenticated",
        "iss": "https://audit.supabase.co/auth/v1",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    claims.pop(missing)
    secret = "synthetic-audit-key-" + "x" * 32
    token = jwt.encode(claims, secret, algorithm="HS256")
    async with httpx.AsyncClient() as client:
        verifier = SupabaseTokenVerifier(audit_settings(supabase_jwt_secret=secret), client)
        with pytest.raises(AuthenticationError):
            await verifier.verify(token)


async def test_validation_errors_do_not_echo_passwords_or_private_fields() -> None:
    from app.main import app

    sentinel = "PRIVATE-SYNTHETIC-PASSWORD-" * 20
    app.dependency_overrides[session_dependency] = lambda: None
    app.dependency_overrides[staff_context] = lambda: SimpleNamespace(role="admin")
    app.dependency_overrides[required_identity] = lambda: VerifiedIdentity(uuid.uuid4(), {})
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://audit"
        ) as client:
            response = await client.patch("/api/v1/staff/profile", json={"password": sentinel})
        assert response.status_code == 422
        assert sentinel not in response.text
        assert "input" not in response.json()["detail"][0]
    finally:
        app.dependency_overrides.clear()


def test_deployed_configuration_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            booking_management_signing_key="x" * 48,
            cors_origins=["*"],
        )


async def test_signed_upload_cannot_replace_existing_evidence() -> None:
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.read())
        return httpx.Response(200, json={"url": "/upload?token=synthetic"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        storage = SupabaseStorageAdminClient(
            client,
            supabase_url="https://audit.supabase.co",
            service_role_key="synthetic",
            bucket="audit",
        )
        await storage.create_signed_upload("business/synthetic.jpg")
    assert b'"upsert":false' in captured[0]


async def test_unknown_signing_keys_do_not_amplify_provider_requests() -> None:
    from test_auth_verifier import jwks, signing_material

    private, public = signing_material("current")
    count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(200, json={"keys": [public]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        verifier = SupabaseTokenVerifier(audit_settings(), client)
        verifier._jwks = jwks(public)
        verifier._jwks_loaded_at = time.monotonic()
        for i in range(4):
            token = jwt.encode(
                {"sub": str(uuid.uuid4())},
                private,
                algorithm="RS256",
                headers={"kid": f"attacker-{i}"},
            )
            with pytest.raises(AuthenticationError):
                await verifier.verify(token)
    assert count <= 1


def test_forged_image_magic_bytes_are_rejected() -> None:
    with pytest.raises(DomainError):
        validate_image(
            b"\xff\xd8\xff" + b"<script>synthetic</script>" + b"\xff\xd9", "image/jpeg", 1000
        )


async def test_storage_content_validation_rejects_lie_about_mime_type() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=b"<html>synthetic</html>")
        )
    ) as client:
        storage = SupabaseStorageAdminClient(
            client,
            supabase_url="https://audit.supabase.co",
            service_role_key="synthetic",
            bucket="audit",
        )
        with pytest.raises(DomainError):
            await storage.validate_uploaded_content("photo.jpg", "image/jpeg", 1024)


async def test_chunked_and_declared_oversized_bodies_are_rejected_before_parsing() -> None:
    from app.core.http_security import MAX_REQUEST_BYTES, SecurityBoundaryMiddleware

    async def no_rate_check(scope):
        pass

    inner = FastAPI()

    @inner.post("/test")
    async def accept():
        raise AssertionError("Oversized input reached the handler")

    secured = SecurityBoundaryMiddleware(inner, no_rate_check)

    async def chunks():
        for _ in range(4):
            yield b"x" * (MAX_REQUEST_BYTES // 3)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=secured), base_url="http://audit"
    ) as client:
        assert (await client.post("/test", content=chunks())).status_code == 413
        assert (
            await client.post(
                "/test", content=b"x", headers={"Content-Length": str(MAX_REQUEST_BYTES + 1)}
            )
        ).status_code == 413


async def test_sensitive_api_responses_prevent_shared_caching() -> None:
    from app.main import app

    app.dependency_overrides[session_dependency] = lambda: None
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://audit"
        ) as client:
            response = await client.get("/api/v1/customer/profile")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_pay_now_fails_closed_without_a_real_payment_adapter() -> None:
    from test_public_schemas import valid_booking_payload

    from app.schemas.public import BookingCreate
    from app.services.bookings import create_booking

    request = BookingCreate.model_validate({**valid_booking_payload(), "payment_choice": "pay_now"})
    with pytest.raises(DomainError) as error:
        await create_booking(None, request, None)
    assert error.value.code == "ONLINE_PAYMENTS_UNAVAILABLE"


def test_customer_cannot_label_a_booking_as_admin_created() -> None:
    from test_public_schemas import valid_booking_payload

    from app.schemas.public import BookingCreate

    with pytest.raises(ValidationError):
        BookingCreate.model_validate({**valid_booking_payload(), "source": "admin"})

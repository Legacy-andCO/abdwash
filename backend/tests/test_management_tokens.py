import uuid

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.services.management_tokens import (
    booking_id_from_management_token,
    create_management_token,
    management_token_hash,
)


def test_management_token_round_trip() -> None:
    booking_id = uuid.uuid4()
    assert booking_id_from_management_token(create_management_token(booking_id)) == booking_id


def test_tampered_management_token_is_rejected() -> None:
    token = create_management_token(uuid.uuid4())
    replacement = "A" if token[-1] != "A" else "B"
    assert booking_id_from_management_token(token[:-1] + replacement) is None


def test_management_token_hash_never_contains_raw_token() -> None:
    token = create_management_token(uuid.uuid4())
    hashed = management_token_hash(token)
    assert token not in hashed
    assert len(hashed) == 64


def test_production_rejects_development_management_key() -> None:
    with pytest.raises(ValidationError, match="BOOKING_MANAGEMENT_SIGNING_KEY"):
        Settings(
            app_env="production",
            database_url="postgresql://localhost/abdwash",
            booking_management_signing_key="development-only-trifecta-management-key",
        )


def test_production_accepts_a_strong_management_key() -> None:
    settings = Settings(
        app_env="production",
        database_url="postgresql://localhost/abdwash",
        booking_management_signing_key="x" * 48,
    )
    assert settings.is_production


def test_management_tokens_are_deterministic_for_idempotent_retries() -> None:
    get_settings.cache_clear()
    booking_id = uuid.uuid4()
    assert create_management_token(booking_id) == create_management_token(booking_id)

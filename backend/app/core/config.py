from email.utils import parseaddr
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Trifecta API"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/abdwash"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    db_pool_size: int = Field(default=5, ge=1, le=20)
    db_max_overflow: int = Field(default=5, ge=0, le=20)
    db_pool_timeout_seconds: float = Field(default=10, gt=0, le=60)
    db_disable_prepared_statements: bool = False
    log_level: str = "INFO"
    booking_management_signing_key: str = "development-only-trifecta-management-key"
    resend_api_key: str | None = None
    email_from: str | None = None
    public_web_url: str | None = None
    outbox_dispatch_secret: str | None = None
    google_routes_api_key: str | None = None
    job_photo_bucket: str = "job-quality-photos"
    job_photo_signed_url_seconds: int = Field(default=300, ge=60, le=3600)
    job_photo_max_bytes: int = Field(default=8_388_608, ge=1024, le=20_971_520)

    supabase_url: str | None = None
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_secret: str | None = None
    supabase_service_role_key: str | None = None
    demo_staff_password: str | None = None
    jwks_cache_ttl_seconds: int = Field(default=600, ge=60, le=3600)

    outbox_poll_seconds: float = Field(default=2, ge=0.1, le=60)
    outbox_batch_size: int = Field(default=20, ge=1, le=100)

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        return value

    @field_validator("email_from")
    @classmethod
    def validate_email_from(cls, value: str | None) -> str | None:
        if value is None:
            return None
        display_name, address = parseaddr(value)
        if display_name.strip().casefold() != "trifecta" or "@" not in address:
            raise ValueError(
                "EMAIL_FROM must use the format 'Trifecta <bookings@verified-domain>'"
            )
        return value

    @model_validator(mode="after")
    def require_production_management_key(self) -> "Settings":
        if self.is_production and self.booking_management_signing_key.startswith("development-"):
            raise ValueError("BOOKING_MANAGEMENT_SIGNING_KEY must be set in production")
        if len(self.booking_management_signing_key) < 32:
            raise ValueError("BOOKING_MANAGEMENT_SIGNING_KEY must be at least 32 characters")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def supabase_issuer(self) -> str | None:
        return self.supabase_url.rstrip("/") + "/auth/v1" if self.supabase_url else None

    @property
    def supabase_jwks_url(self) -> str | None:
        if not self.supabase_url:
            return None
        return self.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()

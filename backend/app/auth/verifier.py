import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from jwt import PyJWKSet

from app.core.config import Settings


class AuthenticationError(Exception):
    pass


@dataclass(frozen=True)
class VerifiedIdentity:
    user_id: uuid.UUID
    claims: dict[str, Any]


class SupabaseTokenVerifier:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.client = client
        self._jwks: PyJWKSet | None = None
        self._jwks_loaded_at = 0.0
        self._lock = asyncio.Lock()

    async def _load_jwks(self, *, force: bool = False) -> PyJWKSet:
        now = time.monotonic()
        if (
            not force
            and self._jwks is not None
            and now - self._jwks_loaded_at < self.settings.jwks_cache_ttl_seconds
        ):
            return self._jwks
        if not self.settings.supabase_jwks_url:
            raise AuthenticationError("Supabase Auth is not configured.")
        async with self._lock:
            now = time.monotonic()
            if (
                not force
                and self._jwks is not None
                and now - self._jwks_loaded_at < self.settings.jwks_cache_ttl_seconds
            ):
                return self._jwks
            response = await self.client.get(self.settings.supabase_jwks_url)
            response.raise_for_status()
            self._jwks = PyJWKSet.from_dict(response.json())
            self._jwks_loaded_at = now
            return self._jwks

    async def verify(self, token: str) -> VerifiedIdentity:
        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get("alg")
            if algorithm == "HS256":
                if not self.settings.supabase_jwt_secret:
                    raise AuthenticationError("Legacy token verification is not configured.")
                payload = jwt.decode(
                    token,
                    self.settings.supabase_jwt_secret,
                    algorithms=["HS256"],
                    audience=self.settings.supabase_jwt_audience,
                    issuer=self.settings.supabase_issuer,
                )
            else:
                payload = await self._verify_asymmetric(token, algorithm)
            subject = payload.get("sub")
            if not subject:
                raise AuthenticationError("Token has no subject.")
            return VerifiedIdentity(user_id=uuid.UUID(subject), claims=payload)
        except AuthenticationError:
            raise
        except (jwt.PyJWTError, ValueError, httpx.HTTPError) as exc:
            raise AuthenticationError("Invalid or expired access token.") from exc

    async def _verify_asymmetric(self, token: str, algorithm: str | None) -> dict[str, Any]:
        if algorithm not in {"RS256", "ES256", "EdDSA"}:
            raise AuthenticationError("Unsupported access-token algorithm.")
        header = jwt.get_unverified_header(token)
        key_id = header.get("kid")
        for force in (False, True):
            jwks = await self._load_jwks(force=force)
            signing_key = next((key for key in jwks.keys if key.key_id == key_id), None)
            if signing_key is not None:
                return jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=[algorithm],
                    audience=self.settings.supabase_jwt_audience,
                    issuer=self.settings.supabase_issuer,
                )
        raise AuthenticationError("No matching Supabase signing key.")

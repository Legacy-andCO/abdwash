import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
import structlog
from jwt import PyJWKSet

from app.core.config import Settings

logger = structlog.get_logger()


class AuthenticationError(Exception):
    pass


class AuthenticationServiceUnavailable(Exception):
    pass


class _JwksRefreshError(Exception):
    def __init__(self, reason: str, *, stale_fallback_allowed: bool) -> None:
        super().__init__(reason)
        self.reason = reason
        self.stale_fallback_allowed = stale_fallback_allowed


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

    def _jwks_is_fresh(self, now: float | None = None) -> bool:
        checked_at = time.monotonic() if now is None else now
        return bool(
            self._jwks is not None
            and checked_at - self._jwks_loaded_at
            < self.settings.jwks_cache_ttl_seconds
        )

    @staticmethod
    def _signing_key(jwks: PyJWKSet | None, key_id: str) -> Any | None:
        if jwks is None:
            return None
        return next((key for key in jwks.keys if key.key_id == key_id), None)

    async def _refresh_jwks(
        self,
        *,
        force: bool = False,
        previous_loaded_at: float | None = None,
    ) -> PyJWKSet:
        if not self.settings.supabase_jwks_url:
            raise AuthenticationServiceUnavailable("Supabase Auth is not configured.")
        async with self._lock:
            if not force and self._jwks_is_fresh():
                logger.info("jwks_cache_hit")
                assert self._jwks is not None
                return self._jwks
            if (
                force
                and previous_loaded_at is not None
                and self._jwks is not None
                and self._jwks_loaded_at > previous_loaded_at
            ):
                logger.info("jwks_cache_hit")
                return self._jwks
            try:
                response = await self.client.get(self.settings.supabase_jwks_url)
                response.raise_for_status()
                refreshed = PyJWKSet.from_dict(response.json())
            except httpx.TimeoutException as exc:
                logger.warning("jwks_refresh_timeout")
                raise _JwksRefreshError(
                    "timeout",
                    stale_fallback_allowed=True,
                ) from exc
            except httpx.RequestError as exc:
                logger.warning(
                    "jwks_refresh_network_error",
                    error_type=type(exc).__name__,
                )
                raise _JwksRefreshError(
                    "network_error",
                    stale_fallback_allowed=True,
                ) from exc
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                logger.warning("jwks_refresh_http_error", status_code=status_code)
                raise _JwksRefreshError(
                    "provider_error",
                    stale_fallback_allowed=status_code >= 500,
                ) from exc
            except (ValueError, KeyError, jwt.PyJWTError) as exc:
                logger.warning(
                    "jwks_refresh_invalid_response",
                    error_type=type(exc).__name__,
                )
                raise _JwksRefreshError(
                    "invalid_response",
                    stale_fallback_allowed=False,
                ) from exc
            self._jwks = refreshed
            self._jwks_loaded_at = time.monotonic()
            logger.info("jwks_refresh_success", key_count=len(refreshed.keys))
            return refreshed

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
        except AuthenticationServiceUnavailable:
            raise
        except AuthenticationError:
            logger.info("genuine_invalid_token")
            raise
        except (jwt.PyJWTError, ValueError) as exc:
            logger.info("genuine_invalid_token", error_type=type(exc).__name__)
            raise AuthenticationError("Invalid or expired access token.") from exc

    async def _verify_asymmetric(
        self, token: str, algorithm: str | None
    ) -> dict[str, Any]:
        if algorithm not in {"RS256", "ES256", "EdDSA"}:
            raise AuthenticationError("Unsupported access-token algorithm.")
        header = jwt.get_unverified_header(token)
        key_id = header.get("kid")
        if not isinstance(key_id, str) or not key_id:
            logger.info("unknown_kid")
            raise AuthenticationError("No matching Supabase signing key.")

        cached_jwks = self._jwks
        cached_key = self._signing_key(cached_jwks, key_id)
        if self._jwks_is_fresh():
            if cached_key is not None:
                logger.info("jwks_cache_hit")
                return self._decode_asymmetric(token, algorithm, cached_key.key)
            logger.info("unknown_kid")
            loaded_at = self._jwks_loaded_at
            try:
                refreshed = await self._refresh_jwks(
                    force=True,
                    previous_loaded_at=loaded_at,
                )
            except _JwksRefreshError as exc:
                raise AuthenticationServiceUnavailable(
                    "Supabase signing keys are temporarily unavailable."
                ) from exc
            refreshed_key = self._signing_key(refreshed, key_id)
            if refreshed_key is None:
                raise AuthenticationError("No matching Supabase signing key.")
            return self._decode_asymmetric(token, algorithm, refreshed_key.key)

        if cached_jwks is not None and cached_key is None:
            logger.info("unknown_kid")
        try:
            refreshed = await self._refresh_jwks()
        except _JwksRefreshError as exc:
            if cached_key is not None and exc.stale_fallback_allowed:
                logger.warning("jwks_stale_fallback", reason=exc.reason)
                return self._decode_asymmetric(token, algorithm, cached_key.key)
            raise AuthenticationServiceUnavailable(
                "Supabase signing keys are temporarily unavailable."
            ) from exc
        refreshed_key = self._signing_key(refreshed, key_id)
        if refreshed_key is None:
            raise AuthenticationError("No matching Supabase signing key.")
        return self._decode_asymmetric(token, algorithm, refreshed_key.key)

    def _decode_asymmetric(
        self,
        token: str,
        algorithm: str,
        signing_key: Any,
    ) -> dict[str, Any]:
        return jwt.decode(
            token,
            signing_key,
            algorithms=[algorithm],
            audience=self.settings.supabase_jwt_audience,
            issuer=self.settings.supabase_issuer,
        )

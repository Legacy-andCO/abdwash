from typing import Any
from urllib.parse import parse_qs, quote, urljoin, urlparse

import httpx

from app.core.providers import observe_provider_call
from app.domain.errors import DomainError


class SupabaseStorageAdminClient:
    """Server-only adapter for private job-photo upload and access grants."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        supabase_url: str | None,
        service_role_key: str | None,
        bucket: str,
    ) -> None:
        if not supabase_url or not service_role_key:
            raise DomainError(
                "JOB_PHOTO_STORAGE_UNAVAILABLE",
                "Job photo storage is not configured.",
                status_code=503,
            )
        self.client = client
        self.base_url = supabase_url.rstrip("/")
        self.bucket = bucket
        self.headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
        }

    def _object_path(self, path: str) -> str:
        return f"{quote(self.bucket, safe='')}/{quote(path, safe='/')}"

    async def create_signed_upload(self, path: str, *, upsert: bool = True) -> str:
        try:
            response = await observe_provider_call(
                "supabase_storage",
                "sign_upload",
                lambda: self.client.post(
                    f"{self.base_url}/storage/v1/object/upload/sign/{self._object_path(path)}",
                    headers=self.headers,
                    json={"upsert": upsert},
                ),
            )
        except httpx.HTTPError as exc:
            raise self._unavailable() from exc
        self._raise(response, "JOB_PHOTO_UPLOAD_GRANT_FAILED")
        payload = response.json()
        signed_path = str(payload.get("url") or payload.get("signedURL") or "")
        token = parse_qs(urlparse(signed_path).query).get("token", [None])[0]
        if not token:
            raise DomainError(
                "JOB_PHOTO_UPLOAD_GRANT_FAILED",
                "Photo upload could not be authorized.",
                status_code=502,
            )
        return token

    async def object_info(self, path: str) -> dict[str, Any]:
        try:
            response = await observe_provider_call(
                "supabase_storage",
                "object_info",
                lambda: self.client.get(
                    f"{self.base_url}/storage/v1/object/info/{self._object_path(path)}",
                    headers=self.headers,
                ),
            )
        except httpx.HTTPError as exc:
            raise self._unavailable() from exc
        self._raise(response, "JOB_PHOTO_UPLOAD_NOT_FOUND")
        return dict(response.json())

    async def create_signed_download(self, path: str, expires_in: int) -> str:
        try:
            response = await observe_provider_call(
                "supabase_storage",
                "sign_download",
                lambda: self.client.post(
                    f"{self.base_url}/storage/v1/object/sign/{self._object_path(path)}",
                    headers=self.headers,
                    json={"expiresIn": expires_in},
                ),
            )
        except httpx.HTTPError as exc:
            raise self._unavailable() from exc
        self._raise(response, "JOB_PHOTO_ACCESS_FAILED")
        signed_path = str(response.json().get("signedURL") or "")
        if not signed_path:
            raise DomainError(
                "JOB_PHOTO_ACCESS_FAILED",
                "Photo access could not be authorized.",
                status_code=502,
            )
        return urljoin(f"{self.base_url}/storage/v1/", signed_path.lstrip("/"))

    @staticmethod
    def _raise(response: httpx.Response, code: str) -> None:
        if response.is_success:
            return
        raise DomainError(
            code,
            "Supabase could not complete the photo operation.",
            status_code=502,
        )

    @staticmethod
    def _unavailable() -> DomainError:
        return DomainError(
            "JOB_PHOTO_STORAGE_UNAVAILABLE",
            "Photo storage is temporarily unavailable.",
            status_code=503,
        )

import uuid
from typing import Any

import httpx

from app.domain.errors import ConflictError, DomainError
from app.domain.staff_usernames import normalize_staff_username, staff_synthetic_email


class SupabaseAdminClient:
    """Small server-only adapter around Supabase Auth Admin endpoints."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        supabase_url: str | None,
        service_role_key: str | None,
    ) -> None:
        if not supabase_url or not service_role_key:
            raise DomainError(
                "STAFF_AUTH_UNAVAILABLE",
                "Staff account management is not configured.",
                status_code=503,
            )
        self.client = client
        self.base_url = supabase_url.rstrip("/")
        self.headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
        }

    async def find_by_email(self, email: str) -> dict[str, Any] | None:
        page = 1
        while True:
            response = await self.client.get(
                f"{self.base_url}/auth/v1/admin/users",
                headers=self.headers,
                params={"page": page, "per_page": 1000},
            )
            self._raise(response, "STAFF_AUTH_LOOKUP_FAILED")
            users = response.json().get("users", [])
            match = next(
                (user for user in users if str(user.get("email", "")).lower() == email),
                None,
            )
            if match is not None or len(users) < 1000:
                return match
            page += 1

    async def create_staff_user(self, username: str, password: str) -> uuid.UUID:
        normalized = normalize_staff_username(username)
        response = await self.client.post(
            f"{self.base_url}/auth/v1/admin/users",
            headers=self.headers,
            json=self._body(normalized, password),
        )
        if response.status_code in {400, 409, 422} and any(
            marker in response.text.lower()
            for marker in ("already", "registered", "exists")
        ):
            raise ConflictError("USERNAME_TAKEN", "That username is already in use.")
        self._raise(response, "STAFF_AUTH_CREATE_FAILED")
        return self._user_id(response)

    async def ensure_staff_user(self, username: str, password: str) -> uuid.UUID:
        normalized = normalize_staff_username(username)
        existing = await self.find_by_email(staff_synthetic_email(normalized))
        if existing is None:
            return await self.create_staff_user(normalized, password)
        user_id = uuid.UUID(str(existing["id"]))
        await self.update_staff_user(user_id, username=normalized, password=password)
        return user_id

    async def update_staff_user(
        self,
        user_id: uuid.UUID,
        *,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        body: dict[str, Any] = {}
        if username is not None:
            normalized = normalize_staff_username(username)
            body.update(
                {
                    "email": staff_synthetic_email(normalized),
                    "email_confirm": True,
                    "app_metadata": {
                        "account_type": "staff",
                        "staff_username": normalized,
                    },
                }
            )
        if password is not None:
            body["password"] = password
        response = await self.client.put(
            f"{self.base_url}/auth/v1/admin/users/{user_id}",
            headers=self.headers,
            json=body,
        )
        self._raise(response, "STAFF_AUTH_UPDATE_FAILED")

    async def delete_staff_user(self, user_id: uuid.UUID) -> None:
        response = await self.client.delete(
            f"{self.base_url}/auth/v1/admin/users/{user_id}",
            headers=self.headers,
        )
        self._raise(response, "STAFF_AUTH_COMPENSATION_FAILED")

    @staticmethod
    def _body(username: str, password: str) -> dict[str, Any]:
        return {
            "email": staff_synthetic_email(username),
            "password": password,
            "email_confirm": True,
            "app_metadata": {
                "account_type": "staff",
                "staff_username": username,
            },
        }

    @staticmethod
    def _user_id(response: httpx.Response) -> uuid.UUID:
        payload = response.json()
        user = payload.get("user", payload)
        return uuid.UUID(str(user["id"]))

    @staticmethod
    def _raise(response: httpx.Response, code: str) -> None:
        if response.is_success:
            return
        raise DomainError(
            code,
            "Supabase could not complete the staff account operation.",
            status_code=502,
        )

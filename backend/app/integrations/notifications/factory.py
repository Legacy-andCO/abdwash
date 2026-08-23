from typing import Any

import httpx

from app.core.config import Settings
from app.integrations.notifications.base import NotificationProvider
from app.integrations.notifications.log import LogNotificationProvider
from app.integrations.notifications.resend import ResendNotificationProvider


class UnavailableNotificationProvider:
    async def send(
        self,
        *,
        channel: str,
        recipient: str,
        notification_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> None:
        raise RuntimeError("Transactional email delivery is not configured")


def create_notification_provider(
    settings: Settings, client: httpx.AsyncClient
) -> NotificationProvider:
    if settings.resend_api_key and settings.email_from and settings.public_web_url:
        return ResendNotificationProvider(
            client,
            api_key=settings.resend_api_key,
            email_from=settings.email_from,
        )
    if settings.is_production:
        return UnavailableNotificationProvider()
    return LogNotificationProvider()

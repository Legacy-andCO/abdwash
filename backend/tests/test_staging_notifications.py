import httpx

from app.core.config import Settings
from app.integrations.notifications.factory import create_notification_provider
from app.integrations.notifications.log import LogNotificationProvider


async def test_staging_cannot_send_real_mail_even_with_inherited_provider_credentials():
    config = Settings(
        _env_file=None,
        app_env="staging",
        booking_management_signing_key="synthetic-stage-key-" + "x" * 32,
        cors_origins=["https://staging.example.com"],
        resend_api_key="synthetic-only",
        email_from="Trifecta <bookings@example.com>",
        public_web_url="https://staging.example.com",
    )
    async with httpx.AsyncClient() as client:
        assert isinstance(create_notification_provider(config, client), LogNotificationProvider)

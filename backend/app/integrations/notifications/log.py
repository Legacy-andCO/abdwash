from typing import Any

import structlog

logger = structlog.get_logger()


class LogNotificationProvider:
    async def send(
        self,
        *,
        channel: str,
        recipient: str,
        notification_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> None:
        logger.info(
            "development_notification",
            channel=channel,
            recipient_hint=_mask_recipient(recipient),
            notification_type=notification_type,
            booking_reference=payload.get("booking_reference"),
        )


def _mask_recipient(recipient: str) -> str:
    if "@" in recipient:
        name, domain = recipient.split("@", 1)
        return f"{name[:1]}***@{domain}"
    return f"***{recipient[-4:]}" if len(recipient) >= 4 else "***"

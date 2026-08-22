from typing import Any, Protocol


class NotificationProvider(Protocol):
    async def send(
        self, *, channel: str, recipient: str, notification_type: str, payload: dict[str, Any]
    ) -> None: ...

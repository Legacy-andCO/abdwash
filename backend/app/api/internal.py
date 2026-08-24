import hmac
import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.domain.errors import DomainError
from app.integrations.notifications.base import NotificationProvider
from app.workers.notifications import dispatch_once

router = APIRouter(prefix="/api/v1/internal", tags=["internal"])


@router.post("/notifications/dispatch")
async def dispatch_notifications(
    request: Request,
    supplied_secret: Annotated[str | None, Header(alias="X-Outbox-Dispatch-Secret")] = None,
) -> dict[str, int]:
    settings = get_settings()
    expected_secret = settings.outbox_dispatch_secret
    if not expected_secret:
        raise DomainError(
            "NOTIFICATION_DISPATCH_UNAVAILABLE",
            "Notification dispatch is not configured.",
            status_code=503,
        )
    if not supplied_secret or not hmac.compare_digest(supplied_secret, expected_secret):
        raise DomainError("UNAUTHORIZED", "Invalid dispatch credentials.", status_code=401)

    factory = cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)
    provider = cast(NotificationProvider, request.app.state.notification_provider)
    return await dispatch_once(
        factory,
        provider,
        worker_id=f"request-{uuid.uuid4()}",
        batch_size=settings.outbox_batch_size,
        public_web_url=settings.public_web_url,
    )

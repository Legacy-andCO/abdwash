"""Cross-process public API counters; caller headers never determine identity."""

import hashlib
import hmac
import ipaddress
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DomainError


async def consume_api_attempt(
    session: AsyncSession, secret: str, peer: str, *, write: bool
) -> None:
    try:
        address = ipaddress.ip_address(peer)
        peer = (
            str(ipaddress.ip_network(f"{address}/64", strict=False))
            if address.version == 6
            else str(address)
        )
    except ValueError:
        peer = "unknown"
    digest = hmac.new(secret.encode(), peer.encode(), hashlib.sha256).hexdigest()
    now = datetime.now(UTC)
    window = now.replace(second=0, microsecond=0)
    if write:
        window = window.replace(minute=(window.minute // 10) * 10)
    kind = "write" if write else "read"
    for scope, limit in (
        (f"{kind}:all", 300 if write else 2000),
        (f"{kind}:{digest}", 12 if write else 120),
    ):
        accepted = await session.scalar(
            text("""
            INSERT INTO public.api_rate_windows(scope, window_start, attempts)
            VALUES (:scope, :window, 1)
            ON CONFLICT (scope, window_start) DO UPDATE
            SET attempts = api_rate_windows.attempts + 1
            WHERE api_rate_windows.attempts < :limit
            RETURNING attempts
        """),
            {"scope": scope, "window": window, "limit": limit},
        )
        if accepted is None:
            raise DomainError(
                "API_RATE_LIMIT", "Too many attempts. Please try later.", status_code=429
            )
    await session.execute(
        text("DELETE FROM public.api_rate_windows WHERE window_start < :cutoff"),
        {"cutoff": now - timedelta(hours=1)},
    )

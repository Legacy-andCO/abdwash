import time
from collections.abc import Awaitable, Callable

import httpx
import structlog

from app.core.database import request_database_metrics

logger = structlog.get_logger()


def _outcome(error: BaseException | None, result: object | None) -> str:
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    if isinstance(error, httpx.RequestError):
        return "network_error"
    if error is not None:
        return "error"
    if isinstance(result, httpx.Response) and result.status_code >= 500:
        return "http_5xx"
    if isinstance(result, httpx.Response) and result.status_code >= 400:
        return "http_4xx"
    return "success"


async def observe_provider_call[T](
    provider: str,
    operation: str,
    call: Callable[[], Awaitable[T]],
) -> T:
    """Measure one external attempt without logging request data or credentials."""

    started = time.perf_counter()
    error: BaseException | None = None
    result: T | None = None
    try:
        result = await call()
        return result
    except BaseException as exc:
        error = exc
        raise
    finally:
        duration_ms = (time.perf_counter() - started) * 1000
        outcome = _outcome(error, result)
        metrics = request_database_metrics.get()
        if metrics is not None:
            metrics.provider_attempt_count += 1
            metrics.provider_duration_ms += duration_ms
            key = f"{provider}:{outcome}"
            metrics.provider_outcomes[key] = metrics.provider_outcomes.get(key, 0) + 1
        logger.info(
            "provider_attempt",
            provider=provider,
            operation=operation,
            outcome=outcome,
            duration_ms=round(duration_ms, 2),
        )

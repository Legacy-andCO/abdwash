import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import ConflictError
from app.models.entities import IdempotencyRecord


def canonical_request_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


async def find_idempotent_response(
    session: AsyncSession,
    *,
    scope: str,
    operation: str,
    key: str,
    request_hash: str,
) -> IdempotencyRecord | None:
    lock_key = f"idempotency:{scope}:{operation}:{key}"
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": lock_key}
    )
    record = (
        await session.scalars(
            select(IdempotencyRecord).where(
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.idempotency_key == key,
                IdempotencyRecord.expires_at > datetime.now(UTC),
            )
        )
    ).one_or_none()
    if record is not None and record.request_hash != request_hash:
        raise ConflictError(
            "IDEMPOTENCY_CONFLICT",
            "This idempotency key was already used with a different request.",
        )
    return record


def store_idempotent_response(
    session: AsyncSession,
    *,
    scope: str,
    operation: str,
    key: str,
    request_hash: str,
    response_status: int,
    response_json: dict[str, Any],
    resource_id: object | None,
) -> None:
    session.add(
        IdempotencyRecord(
            scope=scope,
            operation=operation,
            idempotency_key=key,
            request_hash=request_hash,
            response_status=response_status,
            response_json=response_json,
            resource_id=resource_id,
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    )

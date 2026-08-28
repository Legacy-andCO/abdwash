import contextvars
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, cast

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, SessionTransaction

from app.core.config import Settings

query_count: contextvars.ContextVar[int] = contextvars.ContextVar("query_count", default=0)
query_duration_ms: contextvars.ContextVar[float] = contextvars.ContextVar(
    "query_duration_ms", default=0.0
)


@dataclass
class RequestDatabaseMetrics:
    """Mutable request metrics shared across Starlette's downstream task boundary.

    A mutable object is intentional: ContextVar value replacement does not cross
    Starlette's task boundary, while mutations to this inherited object do.
    """

    request_started: float
    query_count: int = 0
    query_duration_ms: float = 0.0
    first_query_started_ms: float | None = None
    checkout_count: int = 0
    checkout_duration_ms: float = 0.0
    checkout_wait_started: float | None = None
    pool_checked_out_peak: int = 0
    provider_attempt_count: int = 0
    provider_duration_ms: float = 0.0
    provider_outcomes: dict[str, int] = field(default_factory=dict)


request_database_metrics: contextvars.ContextVar[RequestDatabaseMetrics | None] = (
    contextvars.ContextVar("request_database_metrics", default=None)
)


class TrifectaSyncSession(Session):
    """Synchronous facade used by AsyncSession for request checkout telemetry."""


@event.listens_for(TrifectaSyncSession, "after_transaction_create")
def transaction_created(session: Session, transaction: SessionTransaction) -> None:
    if transaction.parent is not None:
        return
    metrics = request_database_metrics.get()
    if metrics is not None:
        metrics.checkout_wait_started = time.perf_counter()


@event.listens_for(TrifectaSyncSession, "after_transaction_end")
def transaction_ended(session: Session, transaction: SessionTransaction) -> None:
    if transaction.parent is not None:
        return
    metrics = request_database_metrics.get()
    if metrics is not None:
        metrics.checkout_wait_started = None


def create_engine(settings: Settings) -> AsyncEngine:
    connect_args: dict[str, object] = {"server_settings": {"application_name": "trifecta-api"}}
    if settings.db_disable_prepared_statements:
        connect_args.update(prepared_statement_cache_size=0, statement_cache_size=0)
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=settings.db_pool_pre_ping,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_use_lifo=True,
        connect_args=connect_args,
    )

    @event.listens_for(engine.sync_engine.pool, "checkout")
    def pool_checkout(*args: object) -> None:
        metrics = request_database_metrics.get()
        if metrics is None:
            return
        metrics.checkout_count += 1
        if metrics.checkout_wait_started is not None:
            metrics.checkout_duration_ms += (
                time.perf_counter() - metrics.checkout_wait_started
            ) * 1000
            metrics.checkout_wait_started = None
        checked_out = getattr(engine.sync_engine.pool, "checkedout", None)
        if callable(checked_out):
            metrics.pool_checked_out_peak = max(
                metrics.pool_checked_out_peak,
                int(checked_out()),
            )

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def before_cursor_execute(conn: Any, *args: object) -> None:
        metrics = request_database_metrics.get()
        if metrics is not None:
            metrics.query_count += 1
            if metrics.first_query_started_ms is None:
                metrics.first_query_started_ms = (
                    time.perf_counter() - metrics.request_started
                ) * 1000
        query_count.set(query_count.get() + 1)
        conn._trifecta_query_started = time.perf_counter()

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def after_cursor_execute(conn: Any, *args: object) -> None:
        started = getattr(conn, "_trifecta_query_started", None)
        if started is not None:
            elapsed = (time.perf_counter() - started) * 1000
            metrics = request_database_metrics.get()
            if metrics is not None:
                metrics.query_duration_ms += elapsed
            query_duration_ms.set(query_duration_ms.get() + elapsed)

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        sync_session_class=TrifectaSyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def session_dependency(request: Request) -> AsyncIterator[AsyncSession]:
    factory = cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)
    async with factory() as session:
        yield session

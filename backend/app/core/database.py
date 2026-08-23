import contextvars
import time
from collections.abc import AsyncIterator
from typing import Any, cast

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings

query_count: contextvars.ContextVar[int] = contextvars.ContextVar("query_count", default=0)
query_duration_ms: contextvars.ContextVar[float] = contextvars.ContextVar(
    "query_duration_ms", default=0.0
)


def create_engine(settings: Settings) -> AsyncEngine:
    connect_args: dict[str, object] = {"server_settings": {"application_name": "abdwash-api"}}
    if settings.db_disable_prepared_statements:
        connect_args.update(prepared_statement_cache_size=0, statement_cache_size=0)
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        connect_args=connect_args,
    )

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def before_cursor_execute(conn: Any, *args: object) -> None:
        query_count.set(query_count.get() + 1)
        conn._abdwash_query_started = time.perf_counter()

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def after_cursor_execute(conn: Any, *args: object) -> None:
        started = getattr(conn, "_abdwash_query_started", None)
        if started is not None:
            elapsed = (time.perf_counter() - started) * 1000
            query_duration_ms.set(query_duration_ms.get() + elapsed)

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)


async def session_dependency(request: Request) -> AsyncIterator[AsyncSession]:
    factory = cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)
    async with factory() as session:
        yield session

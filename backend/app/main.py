import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

from app.api.public import router as public_router
from app.api.staff import router as staff_router
from app.api.system import router as system_router
from app.auth.verifier import SupabaseTokenVerifier
from app.core.config import get_settings
from app.core.database import (
    create_engine,
    create_session_factory,
    query_count,
    query_duration_ms,
)
from app.core.logging import configure_logging
from app.domain.errors import DomainError
from app.integrations.notifications.log import LogNotificationProvider

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    engine = create_engine(settings)
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5, read=10, write=10, pool=5),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.http_client = http_client
    app.state.auth_verifier = SupabaseTokenVerifier(settings, http_client)
    app.state.notification_provider = LogNotificationProvider()
    yield
    await http_client.aclose()
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "X-Booking-Management-Token",
        "X-Request-ID",
    ],
)


@app.middleware("http")
async def request_metrics(request: Request, call_next: Any) -> Any:
    supplied_request_id = request.headers.get("x-request-id")
    try:
        request_id = (
            str(uuid.UUID(supplied_request_id)) if supplied_request_id else str(uuid.uuid4())
        )
    except ValueError:
        request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    count_token = query_count.set(0)
    duration_token = query_duration_ms.set(0.0)
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        if not settings.is_production:
            response.headers["X-SQL-Query-Count"] = str(query_count.get())
            response.headers["X-SQL-Duration-Ms"] = f"{query_duration_ms.get():.2f}"
        return response
    finally:
        route = request.scope.get("route")
        safe_route = getattr(route, "path", request.url.path)
        logger.info(
            "http_request",
            request_id=request_id,
            method=request.method,
            route=safe_route,
            status=status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            sql_query_count=query_count.get(),
            sql_duration_ms=round(query_duration_ms.get(), 2),
        )
        query_count.reset(count_token)
        query_duration_ms.reset(duration_token)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "request_id": getattr(request.state, "request_id", None),
            "details": exc.details,
        },
    )


@app.exception_handler(DBAPIError)
async def database_error_handler(request: Request, exc: DBAPIError) -> JSONResponse:
    logger.error(
        "database_error",
        request_id=getattr(request.state, "request_id", None),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=503,
        content={
            "code": "DATABASE_UNAVAILABLE",
            "message": "A required dependency is unavailable.",
            "request_id": getattr(request.state, "request_id", None),
            "details": {},
        },
    )


app.include_router(system_router)
app.include_router(public_router)
app.include_router(staff_router)

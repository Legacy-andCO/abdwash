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
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

from app.api.customer import router as customer_router
from app.api.internal import router as internal_router
from app.api.public import router as public_router
from app.api.staff import router as staff_router
from app.api.system import router as system_router
from app.auth.verifier import SupabaseTokenVerifier
from app.core.config import get_settings
from app.core.database import (
    RequestDatabaseMetrics,
    create_engine,
    create_session_factory,
    query_count,
    query_duration_ms,
    request_database_metrics,
)
from app.core.logging import configure_logging
from app.domain.errors import DomainError
from app.integrations.notifications.factory import create_notification_provider

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger()
process_started = time.perf_counter()
process_has_served_request = False


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
    app.state.notification_provider = create_notification_provider(settings, http_client)
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
    global process_has_served_request
    supplied_request_id = request.headers.get("x-request-id")
    try:
        request_id = (
            str(uuid.UUID(supplied_request_id)) if supplied_request_id else str(uuid.uuid4())
        )
    except ValueError:
        request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    database_metrics = RequestDatabaseMetrics(request_started=started)
    metrics_token = request_database_metrics.set(database_metrics)
    count_token = query_count.set(0)
    duration_token = query_duration_ms.set(0.0)
    cold_process = not process_has_served_request
    status_code = 500
    response_start_ms: float | None = None
    try:
        response = await call_next(request)
        response_start_ms = (time.perf_counter() - started) * 1000
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        auth_ms = float(getattr(request.state, "auth_ms", 0.0))
        staff_context_ms = float(getattr(request.state, "staff_context_ms", 0.0))
        application_ms = max(
            0.0,
            response_start_ms - auth_ms - staff_context_ms,
        )
        timing_parts = [
            f"auth;dur={auth_ms:.2f}",
            f"staff-context;dur={staff_context_ms:.2f}",
            f"db-checkout;dur={database_metrics.checkout_duration_ms:.2f}",
            f"sql;dur={database_metrics.query_duration_ms:.2f}",
            f"providers;dur={database_metrics.provider_duration_ms:.2f}",
            f"app;dur={application_ms:.2f}",
        ]
        if database_metrics.first_query_started_ms is not None:
            timing_parts.append(f"first-sql;dur={database_metrics.first_query_started_ms:.2f}")
        response.headers["Server-Timing"] = ", ".join(timing_parts)
        if not settings.is_production:
            response.headers["X-SQL-Query-Count"] = str(database_metrics.query_count)
            response.headers["X-SQL-Duration-Ms"] = f"{database_metrics.query_duration_ms:.2f}"
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
            response_start_ms=(
                round(response_start_ms, 2) if response_start_ms is not None else None
            ),
            sql_query_count=database_metrics.query_count,
            sql_duration_ms=round(database_metrics.query_duration_ms, 2),
            db_checkout_count=database_metrics.checkout_count,
            db_checkout_ms=round(database_metrics.checkout_duration_ms, 2),
            db_pool_checked_out_peak=database_metrics.pool_checked_out_peak,
            first_sql_started_ms=(
                round(database_metrics.first_query_started_ms, 2)
                if database_metrics.first_query_started_ms is not None
                else None
            ),
            auth_ms=round(float(getattr(request.state, "auth_ms", 0.0)), 2),
            staff_context_ms=round(float(getattr(request.state, "staff_context_ms", 0.0)), 2),
            provider_attempt_count=database_metrics.provider_attempt_count,
            provider_duration_ms=round(database_metrics.provider_duration_ms, 2),
            provider_outcomes=database_metrics.provider_outcomes,
            cold_process=cold_process,
            process_age_ms=round((time.perf_counter() - process_started) * 1000, 2),
        )
        process_has_served_request = True
        query_count.reset(count_token)
        query_duration_ms.reset(duration_token)
        request_database_metrics.reset(metrics_token)


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
@app.exception_handler(SQLAlchemyTimeoutError)
async def database_error_handler(
    request: Request, exc: DBAPIError | SQLAlchemyTimeoutError
) -> JSONResponse:
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
app.include_router(internal_router)
app.include_router(public_router)
app.include_router(customer_router)
app.include_router(staff_router)

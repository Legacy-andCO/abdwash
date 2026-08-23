import uuid

import pytest
from fastapi.testclient import TestClient

import app.api.public as public_api
from app.auth.dependencies import StaffContext, staff_context
from app.domain.enums import StaffRole
from app.main import app
from app.schemas.public import CatalogueResponse


def test_health_is_lightweight() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-sql-query-count"] == "0"
    assert response.headers.get("x-request-id")


class StubSession:
    async def __aenter__(self) -> "StubSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


def test_catalogue_injects_request_scoped_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = StubSession()
    received_sessions: list[object] = []

    async def fake_get_catalogue(received_session: object) -> CatalogueResponse:
        received_sessions.append(received_session)
        return CatalogueResponse.model_validate(
            {
                "business_name": "AbdWash",
                "settings": {
                    "timezone": "Asia/Dubai",
                    "currency_code": "AED",
                    "opening_time": "09:00:00",
                    "closing_time": "21:00:00",
                    "slot_duration_minutes": 120,
                    "multi_vehicle_threshold": 3,
                    "multi_vehicle_required_slots": 2,
                    "hold_duration_minutes": 10,
                    "cancellation_cutoff_hours": 24,
                },
                "services": [],
            }
        )

    monkeypatch.setattr(public_api, "get_catalogue", fake_get_catalogue)

    with TestClient(app) as client:
        app.state.session_factory = lambda: session
        response = client.get("/api/v1/public/catalogue")

    assert response.status_code == 200
    assert response.status_code != 422
    assert received_sessions == [session]


def test_unauthorized_staff_route() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/staff/context")
    assert response.status_code == 401


def _context(role: StaffRole) -> StaffContext:
    return StaffContext(
        auth_user_id=uuid.uuid4(),
        staff_id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        business_name="AbdWash",
        role=role,
        timezone="Asia/Dubai",
    )


def test_employee_staff_context_authorized() -> None:
    app.dependency_overrides[staff_context] = lambda: _context(StaffRole.EMPLOYEE)
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/staff/context")
        assert response.status_code == 200
        assert response.json()["role"] == "employee"
    finally:
        app.dependency_overrides.clear()


def test_manager_route_rejects_employee() -> None:
    app.dependency_overrides[staff_context] = lambda: _context(StaffRole.EMPLOYEE)
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/staff/management-check")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_manager_route_accepts_manager_and_admin() -> None:
    for role in (StaffRole.MANAGER, StaffRole.ADMIN):
        app.dependency_overrides[staff_context] = lambda role=role: _context(role)
        try:
            with TestClient(app) as client:
                response = client.get("/api/v1/staff/management-check")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()


class FailingSession:
    async def __aenter__(self) -> "FailingSession":
        raise OSError("database unavailable")

    async def __aexit__(self, *args: object) -> None:
        return None


def test_readiness_returns_503_when_database_is_unavailable() -> None:
    with TestClient(app) as client:
        app.state.session_factory = lambda: FailingSession()
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["code"] == "NOT_READY"


def test_malformed_booking_is_rejected_before_business_logic() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/public/bookings",
            json={"payment_status": "paid", "total_amount_minor": 1},
            headers={"Idempotency-Key": "malformed-request"},
        )
    assert response.status_code == 422

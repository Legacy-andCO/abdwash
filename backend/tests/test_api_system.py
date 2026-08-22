import uuid

from fastapi.testclient import TestClient

from app.auth.dependencies import StaffContext, staff_context
from app.domain.enums import StaffRole
from app.main import app


def test_health_is_lightweight() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-sql-query-count"] == "0"
    assert response.headers.get("x-request-id")


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

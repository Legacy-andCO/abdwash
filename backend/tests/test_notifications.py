import json
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

import app.api.internal as internal_api
import app.workers.notifications as notification_worker
from app.core.config import Settings
from app.domain.enums import OutboxStatus
from app.integrations.notifications.log import LogNotificationProvider
from app.integrations.notifications.resend import ResendNotificationProvider, render_email
from app.main import app
from app.models.entities import NotificationOutbox


def confirmation_payload() -> dict[str, Any]:
    return {
        "booking_reference": "AW-ABC123",
        "customer_first_name": "Ahmad",
        "scheduled_start": "2026-08-28T13:00:00+04:00",
        "scheduled_end": "2026-08-28T15:00:00+04:00",
        "timezone": "Asia/Dubai",
        "vehicle_count": 1,
        "vehicles": [{"make": "Toyota", "model": "Camry", "service_name": "Full Wash"}],
        "written_address": "Yas Island, Abu Dhabi",
        "total_amount_minor": 12500,
        "currency_code": "AED",
        "payment_choice": "pay_after_service",
        "payment_status": "unpaid",
        "management_url": "https://abdwash.example/manage#secure-management-token",
        "cancellation_cutoff_hours": 24,
    }


def outbox_record() -> NotificationOutbox:
    return NotificationOutbox(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        channel="email",
        notification_type="booking_confirmed",
        recipient="ahmad@example.com",
        payload={"booking_reference": "AW-ABC123"},
        status=OutboxStatus.PROCESSING,
        attempt_count=0,
        next_attempt_at=datetime.now(UTC),
        locked_at=datetime.now(UTC),
        locked_by="test-worker",
    )


def test_booking_email_contains_reference_and_management_url() -> None:
    subject, html = render_email("booking_confirmed", confirmation_payload())
    assert "AW-ABC123" in subject
    assert "AW-ABC123" in html
    assert "https://abdwash.example/manage#secure-management-token" in html
    assert "Pay after service" in html


@pytest.mark.asyncio
async def test_resend_uses_correct_recipient_and_marks_success_possible() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"id": "email-1"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ResendNotificationProvider(
            client,
            api_key="test-resend-key",
            email_from="AbdWash <bookings@example.com>",
        )
        await provider.send(
            channel="email",
            recipient="ahmad@example.com",
            notification_type="booking_confirmed",
            payload=confirmation_payload(),
            idempotency_key="notification-1",
        )

    body = json.loads(captured[0].content)
    assert body["to"] == ["ahmad@example.com"]
    assert "AW-ABC123" in body["subject"]
    assert captured[0].headers["Idempotency-Key"] == "notification-1"

    record = outbox_record()
    notification_worker.mark_delivery_succeeded(record, now=datetime.now(UTC))
    assert record.status == OutboxStatus.SENT
    assert record.sent_at is not None


@pytest.mark.asyncio
async def test_resend_failure_moves_notification_to_retry() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request, json={"message": "unavailable"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ResendNotificationProvider(
            client,
            api_key="test-resend-key",
            email_from="AbdWash <bookings@example.com>",
        )
        with pytest.raises(httpx.HTTPStatusError) as caught:
            await provider.send(
                channel="email",
                recipient="ahmad@example.com",
                notification_type="booking_confirmed",
                payload=confirmation_payload(),
                idempotency_key="notification-2",
            )

    record = outbox_record()
    notification_worker.mark_delivery_failed(record, caught.value, now=datetime.now(UTC))
    assert record.status == OutboxStatus.RETRY
    assert record.attempt_count == 1
    assert record.next_attempt_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_log_provider_does_not_log_raw_management_token() -> None:
    token = "secure-management-token"  # noqa: S105 - synthetic test value
    with capture_logs() as logs:
        await LogNotificationProvider().send(
            channel="email",
            recipient="ahmad@example.com",
            notification_type="booking_confirmed",
            payload=confirmation_payload(),
            idempotency_key="notification-3",
        )
    assert token not in json.dumps(logs)


def test_internal_dispatch_rejects_missing_and_incorrect_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        app_env="test",
        booking_management_signing_key="x" * 48,
        outbox_dispatch_secret="d" * 48,
    )
    monkeypatch.setattr(internal_api, "get_settings", lambda: settings)
    with TestClient(app) as client:
        missing = client.post("/api/v1/internal/notifications/dispatch")
        incorrect = client.post(
            "/api/v1/internal/notifications/dispatch",
            headers={"X-Outbox-Dispatch-Secret": "wrong"},
        )
    assert missing.status_code == 401
    assert incorrect.status_code == 401


def test_internal_dispatch_runs_one_bounded_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        app_env="test",
        booking_management_signing_key="x" * 48,
        outbox_dispatch_secret="d" * 48,
        outbox_batch_size=3,
        public_web_url="https://abdwash.example",
    )
    calls: list[int] = []

    async def fake_dispatch(*args: object, **kwargs: object) -> dict[str, int]:
        calls.append(int(kwargs["batch_size"]))
        return {"claimed": 3, "sent": 2, "retry": 1, "skipped": 0}

    monkeypatch.setattr(internal_api, "get_settings", lambda: settings)
    monkeypatch.setattr(internal_api, "dispatch_once", fake_dispatch)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/internal/notifications/dispatch",
            headers={"X-Outbox-Dispatch-Secret": "d" * 48},
        )
    assert response.status_code == 200
    assert response.json() == {"claimed": 3, "sent": 2, "retry": 1, "skipped": 0}
    assert calls == [3]

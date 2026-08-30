import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

import app.api.internal as internal_api
import app.workers.notifications as notification_worker
from app.core.config import Settings
from app.domain.enums import OutboxStatus
from app.integrations.notifications.log import LogNotificationProvider
from app.integrations.notifications.resend import (
    ResendDeliveryError,
    ResendNotificationProvider,
    render_email,
)
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
        "management_url": "https://trifecta.example/manage#secure-management-token",
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
    assert "https://trifecta.example/manage#secure-management-token" in html
    assert "Pay after service" in html
    assert "Trifecta" in subject
    assert "TRIFECTA" in html
    assert "AbdWash" not in subject + html
    assert "ABD Wash" not in subject + html
    assert "ADB Wash" not in subject + html


def test_driver_en_route_email_includes_real_eta_and_management_url() -> None:
    payload = confirmation_payload() | {"estimated_arrival_at": "2026-08-28T13:24:00+04:00"}
    subject, html = render_email("driver_en_route", payload)
    assert "on the way" in subject
    assert "Your Trifecta driver is on the way." in html
    assert "13:24" in html
    assert payload["management_url"] in html


def test_driver_en_route_email_without_eta_still_confirms_trip() -> None:
    subject, html = render_email("driver_en_route", confirmation_payload())
    assert "driver is on the way" in subject
    assert "Your Trifecta driver is on the way." in html
    assert "Estimated arrival" not in html


def test_reschedule_email_contains_new_time_and_management_link() -> None:
    payload = confirmation_payload()
    subject, html = render_email("booking_rescheduled", payload)
    assert "rescheduled" in subject.lower()
    assert "28 August 2026" in html
    assert "13:00–15:00" in html
    assert payload["management_url"] in html


@pytest.mark.parametrize(
    "notification_type",
    [
        "booking_confirmed",
        "appointment_reminder",
        "booking_rescheduled",
        "job_completed",
        "driver_en_route",
        "team_delayed",
    ],
)
def test_appointment_emails_render_utc_storage_as_uae_time(
    notification_type: str,
) -> None:
    payload = confirmation_payload() | {
        "scheduled_start": "2026-08-31T06:00:00Z",
        "scheduled_end": "2026-08-31T08:00:00Z",
        "delay_minutes": 30,
    }
    _subject, html = render_email(notification_type, payload)
    assert "10:00" in html
    if notification_type != "job_completed":
        assert "12:00" in html


def test_completion_email_uses_actual_duration_and_authoritative_paid_amount() -> None:
    payload = confirmation_payload() | {
        "actual_service_duration_seconds": 5_700,
        "amount_paid_minor": 13_000,
        "payment_status": "paid",
    }
    subject, html = render_email("job_completed", payload)
    assert "complete" in subject.lower()
    assert "1 hr 35 min" in html
    assert "AED 130.00" in html
    assert "Scheduled service time" in html


def test_completion_email_shows_pending_instead_of_claiming_payment() -> None:
    payload = confirmation_payload() | {
        "actual_service_duration_seconds": None,
        "amount_paid_minor": 0,
        "payment_status": "unpaid",
    }
    _subject, html = render_email("job_completed", payload)
    assert "Payment status" in html
    assert "Pending" in html
    assert "Amount paid" not in html


@pytest.mark.asyncio
async def test_completion_dispatch_payload_uses_reserved_time_actual_elapsed_and_settled_amount(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    business_id, booking_id, payment_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    scheduled_start = datetime(2026, 8, 28, 9, tzinfo=UTC)
    booking = SimpleNamespace(
        id=booking_id,
        business_id=business_id,
        customer_first_name="Ahmad",
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_start + timedelta(hours=2),
        vehicle_count=1,
        written_address="Yas Island",
        total_amount_minor=12_500,
        currency_code="AED",
        payment_choice="pay_after_service",
        payment_status="paid",
    )
    settings = SimpleNamespace(timezone="Asia/Dubai", cancellation_cutoff_hours=24)
    job = SimpleNamespace(
        started_at=scheduled_start + timedelta(minutes=8),
        completed_at=scheduled_start + timedelta(minutes=103),
    )
    payment = SimpleNamespace(
        id=payment_id,
        status="paid",
        method="cash",
        amount_minor=12_500,
    )
    record = outbox_record()
    record.notification_type = "job_completed"
    record.booking_id = booking_id
    session = MagicMock()
    session.get = AsyncMock(return_value=booking)
    settings_result = MagicMock()
    settings_result.one.return_value = settings
    session.scalars = AsyncMock(return_value=settings_result)
    vehicle_result = MagicMock()
    vehicle_result.all.return_value = [("Toyota", "Camry", "Standard Wash")]
    job_payment_result = MagicMock()
    job_payment_result.one.return_value = (job, payment)
    session.execute = AsyncMock(side_effect=[vehicle_result, job_payment_result])
    session.scalar = AsyncMock(return_value=12_500)
    monkeypatch.setattr(notification_worker, "create_management_token", lambda _id: "token")

    payload = await notification_worker.delivery_payload(
        session,
        record,
        public_web_url="https://trifecta.example",
    )

    assert payload["scheduled_start"] == scheduled_start.isoformat()
    assert payload["actual_service_duration_seconds"] == 5_700
    assert payload["amount_paid_minor"] == 12_500
    assert payload["payment_status"] == "paid"


@pytest.mark.asyncio
async def test_delay_dispatch_enriches_current_schedule_without_rescheduling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    booking_id = uuid.uuid4()
    scheduled_start = datetime(2026, 8, 31, 6, tzinfo=UTC)
    booking = SimpleNamespace(
        id=booking_id,
        business_id=uuid.uuid4(),
        customer_first_name="Ahmad",
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_start + timedelta(hours=2),
        vehicle_count=1,
        written_address="Yas Island",
        total_amount_minor=12_500,
        currency_code="AED",
        payment_choice="pay_after_service",
        payment_status="unpaid",
    )
    settings = SimpleNamespace(timezone="Asia/Dubai", cancellation_cutoff_hours=24)
    record = outbox_record()
    record.notification_type = "team_delayed"
    record.booking_id = booking_id
    record.payload = {"booking_reference": "AW-ABC123", "delay_minutes": 30}
    session = MagicMock()
    session.get = AsyncMock(return_value=booking)
    settings_result = MagicMock()
    settings_result.one.return_value = settings
    session.scalars = AsyncMock(return_value=settings_result)
    vehicle_result = MagicMock()
    vehicle_result.all.return_value = [("Toyota", "Camry", "Standard Wash")]
    session.execute = AsyncMock(return_value=vehicle_result)
    monkeypatch.setattr(notification_worker, "create_management_token", lambda _id: "token")

    payload = await notification_worker.delivery_payload(
        session,
        record,
        public_web_url="https://trifecta.example",
    )

    assert payload["delay_minutes"] == 30
    assert payload["scheduled_start"] == "2026-08-31T06:00:00+00:00"
    assert payload["scheduled_end"] == "2026-08-31T08:00:00+00:00"
    assert payload["timezone"] == "Asia/Dubai"
    assert booking.scheduled_start == scheduled_start


def test_cancellation_email_uses_only_current_brand() -> None:
    subject, html = render_email("cancellation_requested", confirmation_payload())
    rendered = subject + html
    assert "Trifecta" in rendered
    assert "AbdWash" not in rendered
    assert "ABD Wash" not in rendered
    assert "ADB Wash" not in rendered


@pytest.mark.parametrize(
    "notification_type",
    [
        "booking_confirmed",
        "driver_en_route",
        "booking_rescheduled",
        "job_completed",
        "cancellation_requested",
        "appointment_reminder",
        "team_arrived",
        "team_delayed",
        "payment_pending",
        "booking_cancelled",
    ],
)
def test_every_transactional_email_uses_only_trifecta_brand(
    notification_type: str,
) -> None:
    subject, html = render_email(
        notification_type, confirmation_payload() | {"delay_minutes": 30}
    )
    rendered = subject + html
    assert "trifecta" in rendered.casefold()
    assert "AbdWash" not in rendered
    assert "ABD Wash" not in rendered
    assert "ADB Wash" not in rendered


@pytest.mark.parametrize(
    ("notification_type", "expected"),
    [
        ("appointment_reminder", "coming up"),
        ("team_arrived", "has arrived"),
        ("team_delayed", "30 minutes late"),
        ("payment_pending", "payment remains pending"),
        ("booking_cancelled", "booking is cancelled"),
    ],
)
def test_operations_emails_are_customer_safe_and_keep_management_link(
    notification_type: str, expected: str
) -> None:
    payload = confirmation_payload() | {"delay_minutes": 30}
    subject, html = render_email(notification_type, payload)
    rendered = f"{subject} {html}".casefold()
    assert expected in rendered
    assert payload["management_url"] in html
    assert "pay now" not in rendered


def test_email_from_requires_trifecta_display_name() -> None:
    settings = Settings(email_from="Trifecta <bookings@example.com>")
    assert settings.email_from == "Trifecta <bookings@example.com>"
    with pytest.raises(ValueError, match="EMAIL_FROM"):
        Settings(email_from="Old Brand <bookings@example.com>")


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
            email_from="Trifecta <bookings@example.com>",
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
    assert body["from"] == "Trifecta <bookings@example.com>"
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
            email_from="Trifecta <bookings@example.com>",
        )
        with pytest.raises(ResendDeliveryError) as caught:
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
async def test_resend_403_retains_only_bounded_sanitized_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            request=request,
            json={
                "name": "validation_error",
                "message": "Testing may only send to private.customer@example.com",
                "statusCode": 403,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ResendNotificationProvider(
            client,
            api_key="test-resend-key",
            email_from="Trifecta <bookings@example.com>",
        )
        with pytest.raises(ResendDeliveryError) as caught:
            await provider.send(
                channel="email",
                recipient="customer@example.com",
                notification_type="team_delayed",
                payload=confirmation_payload() | {"delay_minutes": 30},
                idempotency_key="notification-delay-403",
            )

    assert caught.value.status_code == 403
    assert caught.value.provider_code == "validation_error"
    assert "[email redacted]" in str(caught.value)
    assert "private.customer@example.com" not in str(caught.value)
    record = outbox_record()
    notification_worker.mark_delivery_failed(record, caught.value, now=datetime.now(UTC))
    assert record.status == OutboxStatus.FAILED
    assert record.attempt_count == 1
    assert record.last_error is not None
    assert "Resend 403: validation_error" in record.last_error
    assert "private.customer@example.com" not in record.last_error


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_transient_resend_failures_remain_retryable(status: int) -> None:
    record = outbox_record()
    error = ResendDeliveryError(
        status_code=status,
        provider_code="provider_error",
        message="Temporary provider failure",
    )

    notification_worker.mark_delivery_failed(record, error, now=datetime.now(UTC))

    assert record.status == OutboxStatus.RETRY
    assert record.attempt_count == 1


def test_network_timeout_remains_retryable() -> None:
    record = outbox_record()
    notification_worker.mark_delivery_failed(
        record, httpx.ReadTimeout("provider timeout"), now=datetime.now(UTC)
    )
    assert record.status == OutboxStatus.RETRY


def test_historical_permanent_403_is_not_replayed() -> None:
    assert notification_worker._stored_permanent_resend_failure(
        "ResendDeliveryError: Resend 403: validation_error: Request rejected"
    )
    assert not notification_worker._stored_permanent_resend_failure(
        "ResendDeliveryError: Resend 503: provider_error: Unavailable"
    )


@pytest.mark.asyncio
async def test_delay_and_reminder_use_same_sender_and_recipient_path() -> None:
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, request=request, json={"id": "email"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ResendNotificationProvider(
            client,
            api_key="test-resend-key",
            email_from="Trifecta <bookings@example.com>",
        )
        payload = confirmation_payload()
        await provider.send(
            channel="email",
            recipient="same.customer@example.com",
            notification_type="appointment_reminder",
            payload=payload,
            idempotency_key="reminder-1",
        )
        await provider.send(
            channel="email",
            recipient="same.customer@example.com",
            notification_type="team_delayed",
            payload=payload | {"delay_minutes": 30},
            idempotency_key="delay-1",
        )

    assert [item["to"] for item in captured] == [
        ["same.customer@example.com"],
        ["same.customer@example.com"],
    ]
    assert [item["from"] for item in captured] == [
        "Trifecta <bookings@example.com>",
        "Trifecta <bookings@example.com>",
    ]


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
        public_web_url="https://trifecta.example",
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

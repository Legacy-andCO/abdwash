import base64
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pydantic import ValidationError

import app.api.complaints as complaints_api
import app.api.public as public_api
import app.services.complaints as complaints_service
from app.auth.dependencies import StaffContext, optional_identity, staff_context
from app.auth.verifier import VerifiedIdentity
from app.core.config import Settings
from app.core.database import session_dependency
from app.domain.enums import OutboxStatus, StaffRole
from app.domain.errors import DomainError
from app.integrations.notifications.resend import ResendNotificationProvider, render_email
from app.main import app
from app.models.entities import AuditEvent, CustomerComplaint, NotificationOutbox
from app.schemas.complaints import ComplaintEvidenceInput, ComplaintSubmission
from app.schemas.public import BookingResponse
from app.services.policy_acceptance import POLICY_REVISION, POLICY_VERSIONS
from app.workers.notifications import mark_delivery_failed, mark_delivery_succeeded

REFERENCE = "TC-" + "A" * 32
PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jY1sAAAAASUVORK5CYII="


@asynccontextmanager
async def transaction():
    yield


@pytest.fixture
def session():
    instance = MagicMock()
    instance.begin.side_effect = transaction
    instance.execute = AsyncMock()
    instance.scalar = AsyncMock()
    instance.flush = AsyncMock()
    instance.rollback = AsyncMock()
    return instance


@pytest.fixture
async def api(session, monkeypatch):
    async def get_session():
        yield session

    monkeypatch.setitem(app.dependency_overrides, session_dependency, get_session)
    async with (
        httpx.AsyncClient() as provider,
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        monkeypatch.setattr(app.state, "http_client", provider, raising=False)
        yield client


def booking_payload():
    return {
        "hold_token": "t" * 40,
        "contact": {
            "first_name": "A",
            "surname": "B",
            "phone": "+971501234567",
            "email": "customer@example.com",
        },
        "location": {
            "written_address": "Abu Dhabi",
            "location_url": "https://maps.google.com/?q=Abu+Dhabi",
            "instructions": "Use the main entrance.",
        },
        "vehicles": [
            {
                "make": "Toyota",
                "model": "Camry",
                "vehicle_type": "sedan",
                "plate_number": "A 12345",
                "service_id": str(uuid.uuid4()),
            }
        ],
        "payment_choice": "pay_after_service",
        "source": "admin",
    }


@pytest.mark.parametrize(
    "acceptance,code",
    [
        (None, "POLICY_ACCEPTANCE_REQUIRED"),
        (
            {"accepted": False, "language": "ar", "revision": POLICY_REVISION},
            "POLICY_ACCEPTANCE_REQUIRED",
        ),
        ({"accepted": True, "language": "ar", "revision": "old"}, "POLICY_VERSION_CHANGED"),
    ],
)
async def test_booking_blocks_before_hold_consumption(api, monkeypatch, acceptance, code):
    monkeypatch.setattr(public_api, "find_idempotent_response", AsyncMock(return_value=None))
    create = AsyncMock()
    monkeypatch.setattr(public_api, "create_booking", create)
    result = await api.post(
        "/api/v1/public/bookings",
        json={**booking_payload(), "policy_acceptance": acceptance},
        headers={"Idempotency-Key": "policy-acceptance-test"},
    )
    assert result.status_code in {409, 422}
    assert result.json()["code"] == code
    create.assert_not_called()


@pytest.mark.parametrize("authenticated", [False, True])
async def test_booking_acceptance_written_once_with_server_versions(
    api, session, monkeypatch, authenticated
):
    actor_id = uuid.uuid4() if authenticated else None
    if actor_id is not None:
        monkeypatch.setitem(
            app.dependency_overrides, optional_identity, lambda: VerifiedIdentity(actor_id, {})
        )
    booking = BookingResponse(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        reference="TRI-TEST",
        status="confirmed",
        payment_choice="pay_after_service",
        payment_status="pending",
        scheduled_start=datetime.now(UTC),
        scheduled_end=datetime.now(UTC),
        vehicle_count=1,
        total_amount_minor=5000,
        currency_code="AED",
        customer_first_name="A",
        customer_surname="B",
        written_address="Abu Dhabi",
        location_url="https://maps.google.com",
        location_instructions=None,
        vehicles=[],
        management_token=uuid.uuid4().hex,
    )
    existing = SimpleNamespace(
        resource_id=booking.id, response_json=booking.model_dump(mode="json")
    )
    monkeypatch.setattr(
        public_api, "find_idempotent_response", AsyncMock(side_effect=[None, existing])
    )
    create = AsyncMock(return_value=booking)
    monkeypatch.setattr(public_api, "create_booking", create)
    monkeypatch.setattr(public_api, "bump_sync_revisions", AsyncMock())
    payload = {
        **booking_payload(),
        "policy_acceptance": {"accepted": True, "language": "ar", "revision": POLICY_REVISION},
    }
    for _ in range(2):
        result = await api.post(
            "/api/v1/public/bookings",
            json=payload,
            headers={"Idempotency-Key": "policy-retry-test"},
        )
        assert result.status_code == 201
    create.assert_awaited_once()
    audits = [
        call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], AuditEvent)
    ]
    assert len(audits) == 1
    assert audits[0].entity_id == booking.id
    assert audits[0].actor_auth_user_id == actor_id
    assert audits[0].metadata_json == {
        "channel": "online_checkout",
        "customer_identity": "account" if authenticated else "guest_booking_contact",
        "language": "ar",
        "policy_versions": POLICY_VERSIONS,
    }


def complaint_payload(**changes):
    return {
        "name": "Sample Customer",
        "phone": "+971564204954",
        "category": "damage",
        "description": "Reported a mark on the vehicle after service.",
        "service_date": "2026-10-01",
        "privacy_acknowledged": True,
        "revision": POLICY_REVISION,
        "language": "en",
        **changes,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"phone": None},
        {"privacy_acknowledged": False},
        {"privacy_acknowledged": "true"},
        {"website": "https://spam.example"},
        {"description": "\x00\x01"},
        {"category": "invalid"},
        {"evidence": [{"data": PNG, "content_type": "image/svg+xml"}]},
        {"evidence": [{"data": PNG, "content_type": "image/png"}] * 3},
    ],
)
def test_complaint_validation(changes):
    with pytest.raises(ValidationError):
        ComplaintSubmission.model_validate(complaint_payload(**changes))


async def test_body_limit_and_invalid_data_do_not_echo_personal_information(api, monkeypatch):
    monkeypatch.setattr(complaints_api, "consume_complaint_attempt", AsyncMock())
    headers = {"Idempotency-Key": str(uuid.uuid4()), "Content-Type": "application/json"}
    endpoint = "/api/v1/public/complaints"
    oversized = await api.post(
        endpoint, content=b" " * (complaints_api.MAX_COMPLAINT_BODY + 1), headers=headers
    )
    assert oversized.status_code == 413
    invalid = await api.post(
        endpoint, json=complaint_payload(privacy_acknowledged=False), headers=headers
    )
    assert invalid.status_code == 422
    assert "Sample Customer" not in invalid.text
    assert "+971564204954" not in invalid.text


async def test_rate_limit_stops_the_request_before_upload(api, session):
    session.scalar.side_effect = [1, None]
    response = await api.post(
        "/api/v1/public/complaints",
        json=complaint_payload(),
        headers={"Idempotency-Key": str(uuid.uuid4()), "X-Forwarded-For": "1.2.3.4"},
    )
    assert response.status_code == 429
    query = session.scalar.await_args.args[0]
    assert query.compile().params["scope"] != "1.2.3.4"


def test_photo_must_match_its_mime_type():
    assert complaints_service.decode_evidence(
        ComplaintEvidenceInput(data=PNG, content_type="image/png")
    ) == (base64.b64decode(PNG), "png")
    with pytest.raises(DomainError, match="Attach up to two"):
        complaints_service.decode_evidence(
            ComplaintEvidenceInput(data=PNG, content_type="image/jpeg")
        )


async def test_complaint_saves_late_report_and_queues_reference_only(api, session, monkeypatch):
    business_id = uuid.uuid4()
    monkeypatch.setattr(
        complaints_service,
        "load_default_business",
        AsyncMock(return_value=SimpleNamespace(business=SimpleNamespace(id=business_id))),
    )
    monkeypatch.setattr(
        complaints_service, "find_idempotent_response", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(complaints_api, "consume_complaint_attempt", AsyncMock())
    monkeypatch.setattr(complaints_api, "get_settings", lambda: Settings())
    result = await api.post(
        "/api/v1/public/complaints",
        json=complaint_payload(description="Old report.\x00 Please investigate."),
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert result.status_code == 201
    assert list(result.json()) == ["reference"]
    added = [call.args[0] for call in session.add.call_args_list]
    complaint = next(row for row in added if isinstance(row, CustomerComplaint))
    outbox = next(row for row in added if isinstance(row, NotificationOutbox))
    assert complaint.business_id == business_id
    assert complaint.description == "Old report. Please investigate."
    assert outbox.payload == result.json()
    assert outbox.recipient == complaints_service.CONTACT_EMAIL
    assert outbox.status == OutboxStatus.PENDING


async def test_storage_error_does_not_save_or_queue_a_complaint(api, session, monkeypatch):
    monkeypatch.setattr(
        complaints_service,
        "load_default_business",
        AsyncMock(return_value=SimpleNamespace(business=SimpleNamespace(id=uuid.uuid4()))),
    )
    monkeypatch.setattr(
        complaints_service, "find_idempotent_response", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(complaints_api, "consume_complaint_attempt", AsyncMock())
    storage = SimpleNamespace(
        upload_private=AsyncMock(
            side_effect=DomainError("FAILED", "Upload failed", status_code=502)
        ),
        remove_private=AsyncMock(),
    )
    monkeypatch.setattr(complaints_service, "complaint_storage", lambda *_: storage)
    response = await api.post(
        "/api/v1/public/complaints",
        json=complaint_payload(evidence=[{"data": PNG, "content_type": "image/png"}]),
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 502
    assert "reference" not in response.json()
    storage.remove_private.assert_awaited_once()
    session.add.assert_not_called()


async def test_only_management_can_request_signed_evidence(api, session, monkeypatch):
    endpoint = f"/api/v1/staff/complaints/{REFERENCE}/evidence/0/download"
    assert (await api.post(endpoint)).status_code == 401
    business_id = uuid.uuid4()
    role = StaffRole.EMPLOYEE

    async def staff():
        return StaffContext(uuid.uuid4(), uuid.uuid4(), business_id, "Trifecta", role, "Asia/Dubai")

    monkeypatch.setitem(app.dependency_overrides, staff_context, staff)
    assert (await api.post(endpoint)).status_code == 403
    session.scalar.assert_not_called()
    role = StaffRole.MANAGER
    session.scalar.return_value = None
    assert (await api.post(endpoint)).status_code == 404
    assert business_id in session.scalar.await_args.args[0].compile().params.values()
    storage = SimpleNamespace(
        create_signed_download=AsyncMock(
            return_value="https://storage.example/object/sign/photo?token=test"
        )
    )
    monkeypatch.setattr(complaints_api, "complaint_storage", lambda *_: storage)
    session.scalar.return_value = SimpleNamespace(attachment_paths=["private/photo.jpg"])
    response = await api.post(endpoint)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["url"].endswith("&download=")
    storage.create_signed_download.assert_awaited_once_with("private/photo.jpg", 120)


async def test_complaint_resend_contract_and_transient_retry():
    import json

    calls = []
    replies = iter([503, 200])

    def handle(request):
        calls.append(request)
        return httpx.Response(next(replies), json={"id": "sandbox-id"})

    record = NotificationOutbox(status=OutboxStatus.PROCESSING, attempt_count=1)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        provider = ResendNotificationProvider(
            client, api_key="test-key", email_from="Trifecta <sender@example.com>"
        )
        message = {
            "channel": "email",
            "recipient": complaints_service.CONTACT_EMAIL,
            "notification_type": complaints_service.COMPLAINT_NOTIFICATION,
            "payload": {"reference": REFERENCE},
            "idempotency_key": "same-on-retry",
        }
        try:
            await provider.send(**message)
        except RuntimeError as exc:
            mark_delivery_failed(record, exc, now=datetime.now(UTC))
        assert record.status == OutboxStatus.RETRY
        await provider.send(**message)
        mark_delivery_succeeded(record, now=datetime.now(UTC))
    assert record.status == OutboxStatus.SENT
    assert [request.headers["Idempotency-Key"] for request in calls] == ["same-on-retry"] * 2
    assert json.loads(calls[1].content)["to"] == [complaints_service.CONTACT_EMAIL]
    assert REFERENCE in json.loads(calls[1].content)["subject"]


def test_staff_email_contains_policy_links_and_arabic_copy():
    subject, html = render_email(
        "booking_policies_provided",
        {
            "booking_reference": "TRI-TEST",
            "language": "ar",
            "public_web_url": "https://example.com",
        },
    )
    assert "سياسات حجز" in subject
    assert 'lang="ar" dir="rtl"' in html
    assert all(f"https://example.com/{slug}" in html for slug in POLICY_VERSIONS)

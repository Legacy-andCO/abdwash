import base64
import binascii
import hashlib
import hmac
import ipaddress
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.enums import OutboxStatus
from app.domain.errors import DomainError
from app.integrations.supabase_storage import SupabaseStorageAdminClient
from app.models.entities import ComplaintRateWindow, CustomerComplaint, NotificationOutbox
from app.repositories.business import load_default_business
from app.schemas.complaints import (
    MAX_EVIDENCE_BYTES,
    ComplaintEvidenceInput,
    ComplaintReceipt,
    ComplaintSubmission,
)
from app.services.idempotency import (
    canonical_request_hash,
    find_idempotent_response,
    store_idempotent_response,
)
from app.services.policy_acceptance import POLICY_VERSIONS, require_current_revision

CONTACT_EMAIL = "contact@trifecta-wash.com"
COMPLAINT_NOTIFICATION = "customer_complaint_received"
EVIDENCE_BUCKET = "complaint-evidence"
EVIDENCE_URL_SECONDS = 120
logger = structlog.get_logger()


async def consume_complaint_attempt(session: AsyncSession, settings: Settings, peer: str) -> None:
    # ASGI's client address is supplied by the server and its configured trusted proxy layer.
    # Do not read caller-supplied forwarding headers here or retain raw network addresses.
    try:
        address = ipaddress.ip_address(peer)
        network = (
            str(ipaddress.ip_network(f"{address}/64", strict=False))
            if address.version == 6
            else str(address)
        )
    except ValueError:
        network = "unknown"
    peer_scope = hmac.new(
        settings.booking_management_signing_key.encode(),
        f"complaint-rate:{network}".encode(),
        hashlib.sha256,
    ).hexdigest()
    window = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    async with session.begin():
        for scope, limit in (("all", 100), (peer_scope, 6)):
            counter = insert(ComplaintRateWindow).values(
                scope=scope, window_start=window, attempts=1
            )
            accepted = await session.scalar(
                counter.on_conflict_do_update(
                    index_elements=[ComplaintRateWindow.scope, ComplaintRateWindow.window_start],
                    set_={"attempts": ComplaintRateWindow.attempts + 1},
                    where=ComplaintRateWindow.attempts < limit,
                ).returning(ComplaintRateWindow.attempts)
            )
            if accepted is None:
                raise DomainError(
                    "COMPLAINT_RATE_LIMIT", "Too many attempts. Please try later.", status_code=429
                )
        await session.execute(
            delete(ComplaintRateWindow).where(
                ComplaintRateWindow.window_start < window - timedelta(hours=1)
            )
        )


def decode_evidence(item: ComplaintEvidenceInput) -> tuple[bytes, str]:
    try:
        data = base64.b64decode(item.data, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise invalid_evidence() from exc
    if not data or len(data) > MAX_EVIDENCE_BYTES:
        raise invalid_evidence()
    if (
        item.content_type == "image/jpeg"
        and data.startswith(b"\xff\xd8\xff")
        and data.endswith(b"\xff\xd9")
    ):
        return data, "jpg"
    if (
        item.content_type == "image/png"
        and data.startswith(b"\x89PNG\r\n\x1a\n")
        and data.endswith(b"IEND\xaeB\x60\x82")
    ):
        return data, "png"
    if (
        item.content_type == "image/webp"
        and data.startswith(b"RIFF")
        and data[8:16] in {b"WEBPVP8 ", b"WEBPVP8L", b"WEBPVP8X"}
        and int.from_bytes(data[4:8], "little") + 8 == len(data)
    ):
        return data, "webp"
    raise invalid_evidence()


def invalid_evidence() -> DomainError:
    return DomainError(
        "COMPLAINT_EVIDENCE_INVALID",
        "Attach up to two JPEG, PNG or WebP images of 1 MB each.",
        status_code=422,
    )


def complaint_storage(settings: Settings, client: httpx.AsyncClient) -> SupabaseStorageAdminClient:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise DomainError(
            "COMPLAINT_EVIDENCE_UNAVAILABLE",
            "Photo attachments are temporarily unavailable.",
            status_code=503,
        )
    return SupabaseStorageAdminClient(
        client,
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
        bucket=EVIDENCE_BUCKET,
    )


async def submit_complaint(
    session: AsyncSession,
    settings: Settings,
    client: httpx.AsyncClient,
    payload: ComplaintSubmission,
    idempotency_key: uuid.UUID,
) -> ComplaintReceipt:
    request_hash = canonical_request_hash(payload.model_dump(mode="json"))
    async with session.begin():
        existing = await find_idempotent_response(
            session,
            scope="public",
            operation="submit_complaint",
            key=str(idempotency_key),
            request_hash=request_hash,
        )
        if existing is not None:
            return ComplaintReceipt.model_validate(existing.response_json)

        require_current_revision(payload.revision)
        business_id = (await load_default_business(session)).business.id
        complaint_id = uuid.uuid4()
        reference = f"TC-{complaint_id.hex.upper()}"
        evidence = [(item.content_type, *decode_evidence(item)) for item in payload.evidence]
        storage = complaint_storage(settings, client) if evidence else None
        paths: list[str] = []
        try:
            if storage:
                for content_type, data, extension in evidence:
                    path = f"{business_id}/{complaint_id}/{uuid.uuid4()}.{extension}"
                    paths.append(path)
                    await storage.upload_private(path, data, content_type)

            complaint = CustomerComplaint(
                id=complaint_id,
                business_id=business_id,
                reference=reference,
                name=payload.name,
                email=payload.email,
                phone=payload.phone,
                booking_reference=payload.booking_reference or None,
                service_date=payload.service_date,
                category=payload.category,
                description=payload.description,
                language=payload.language,
                privacy_version=POLICY_VERSIONS["privacy-policy"],
                attachment_paths=paths,
            )
            session.add(complaint)
            session.add(
                NotificationOutbox(
                    business_id=business_id,
                    channel="email",
                    notification_type=COMPLAINT_NOTIFICATION,
                    recipient=settings.verified_complaints_inbox or CONTACT_EMAIL,
                    dedupe_key=f"customer-complaint:{complaint_id}",
                    payload={"reference": reference},
                    status=OutboxStatus.PENDING,
                    next_attempt_at=datetime.now(UTC),
                )
            )
            receipt = ComplaintReceipt(reference=reference)
            store_idempotent_response(
                session,
                scope="public",
                operation="submit_complaint",
                key=str(idempotency_key),
                request_hash=request_hash,
                response_status=201,
                response_json=receipt.model_dump(mode="json"),
                resource_id=complaint_id,
            )
            await session.flush()
        except Exception:
            if storage and paths:
                try:
                    await storage.remove_private(paths)
                except DomainError:
                    logger.warning(
                        "complaint_evidence_cleanup_failed", complaint_id=str(complaint_id)
                    )
            raise
        # After a commit error, the database outcome may be unknown. Leave any objects private
        # for reconciliation instead of deleting evidence that might be linked to a saved report.
    return receipt


async def load_complaint(
    session: AsyncSession, business_id: uuid.UUID, reference: str
) -> CustomerComplaint:
    complaint = await session.scalar(
        select(CustomerComplaint).where(
            CustomerComplaint.business_id == business_id,
            CustomerComplaint.reference == reference,
        )
    )
    if complaint is None:
        raise DomainError("COMPLAINT_NOT_FOUND", "Complaint not found.", status_code=404)
    return complaint

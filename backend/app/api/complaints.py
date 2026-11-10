import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Path, Query, Request, Response
from pydantic import ValidationError
from sqlalchemy import select

from app.auth.dependencies import ManagerContext, SessionDep
from app.core.config import get_settings
from app.domain.errors import DomainError
from app.models.entities import CustomerComplaint, NotificationOutbox
from app.schemas.complaints import (
    MAX_COMPLAINT_BODY,
    ComplaintDetail,
    ComplaintDownload,
    ComplaintReceipt,
    ComplaintSubmission,
    ComplaintSummary,
)
from app.services.complaints import (
    EVIDENCE_URL_SECONDS,
    complaint_storage,
    consume_complaint_attempt,
    load_complaint,
    submit_complaint,
)

public_router = APIRouter(prefix="/api/v1/public/complaints", tags=["public"])
manager_router = APIRouter(prefix="/api/v1/staff/complaints", tags=["staff"])
Reference = Annotated[str, Path(pattern=r"^TC-[0-9A-F]{32}$")]


@public_router.post("", response_model=ComplaintReceipt, status_code=201)
async def create_complaint(
    request: Request,
    response: Response,
    session: SessionDep,
    idempotency_key: Annotated[uuid.UUID, Header(alias="Idempotency-Key")],
) -> ComplaintReceipt:
    response.headers["Cache-Control"] = "no-store"
    settings = get_settings()
    await consume_complaint_attempt(
        session, settings, request.client.host if request.client else "unknown"
    )
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
        raise DomainError("COMPLAINT_CONTENT_TYPE", "Expected JSON.", status_code=415)
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_COMPLAINT_BODY:
            raise DomainError("COMPLAINT_TOO_LARGE", "Attachments are too large.", status_code=413)
        body.extend(chunk)
    try:
        payload = ComplaintSubmission.model_validate_json(body)
    except ValidationError as exc:
        # Do not reflect complaint text, personal data or photo bytes in validation responses.
        raise DomainError(
            "COMPLAINT_INVALID", "Check the form fields and try again.", status_code=422
        ) from exc
    return await submit_complaint(
        session, settings, request.app.state.http_client, payload, idempotency_key
    )


@manager_router.get("", response_model=list[ComplaintSummary])
async def complaints(
    response: Response,
    session: SessionDep,
    context: ManagerContext,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> list[ComplaintSummary]:
    response.headers["Cache-Control"] = "no-store"
    rows = await session.scalars(
        select(CustomerComplaint)
        .where(CustomerComplaint.business_id == context.business_id)
        .order_by(CustomerComplaint.created_at.desc(), CustomerComplaint.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [ComplaintSummary.model_validate(row, from_attributes=True) for row in rows]


@manager_router.get("/{reference}", response_model=ComplaintDetail)
async def complaint_detail(
    reference: Reference, response: Response, session: SessionDep, context: ManagerContext
) -> ComplaintDetail:
    response.headers["Cache-Control"] = "no-store"
    complaint = await load_complaint(session, context.business_id, reference)
    notification_status = await session.scalar(
        select(NotificationOutbox.status).where(
            NotificationOutbox.business_id == context.business_id,
            NotificationOutbox.dedupe_key == f"customer-complaint:{complaint.id}",
        )
    )
    return ComplaintDetail(
        **ComplaintSummary.model_validate(complaint, from_attributes=True).model_dump(),
        name=complaint.name,
        email=complaint.email,
        phone=complaint.phone,
        booking_reference=complaint.booking_reference,
        service_date=complaint.service_date,
        description=complaint.description,
        language=complaint.language,
        privacy_version=complaint.privacy_version,
        attachment_count=len(complaint.attachment_paths),
        notification_status=notification_status,
    )


@manager_router.post("/{reference}/evidence/{index}/download", response_model=ComplaintDownload)
async def complaint_evidence_download(
    reference: Reference,
    index: Annotated[int, Path(ge=0, le=1)],
    request: Request,
    response: Response,
    session: SessionDep,
    context: ManagerContext,
) -> ComplaintDownload:
    response.headers["Cache-Control"] = "no-store"
    complaint = await load_complaint(session, context.business_id, reference)
    if index >= len(complaint.attachment_paths):
        raise DomainError("COMPLAINT_EVIDENCE_NOT_FOUND", "Evidence not found.", status_code=404)
    path = complaint.attachment_paths[index]
    await session.rollback()
    storage = complaint_storage(get_settings(), request.app.state.http_client)
    url = await storage.create_signed_download(path, EVIDENCE_URL_SECONDS)
    return ComplaintDownload(url=f"{url}&download=", expires_in=EVIDENCE_URL_SECONDS)

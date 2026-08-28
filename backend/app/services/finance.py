import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.auth.dependencies import StaffContext
from app.domain.errors import ConflictError, DomainError
from app.models.entities import (
    AuditEvent,
    Booking,
    BusinessSettings,
    CashReconciliation,
    CashReconciliationPayment,
    Expense,
    Job,
    Payment,
    PaymentTransaction,
    ScheduleResource,
    StaffProfile,
)
from app.schemas.finance import (
    CashPendingDetail,
    CashPendingList,
    CashPendingPayment,
    CashPendingStaff,
    CashReconciliationCreate,
    CashReconciliationList,
    CashReconciliationView,
    ExpenseCategoryTotal,
    ExpenseCreate,
    ExpenseList,
    ExpenseView,
    FinanceOverview,
    FinanceSeriesPoint,
    PersonalCashSummary,
    TeamContribution,
)


def _bounds(start_date: date, end_date: date, timezone: str) -> tuple[datetime, datetime]:
    if end_date < start_date or (end_date - start_date).days > 366:
        raise DomainError(
            "INVALID_FINANCE_RANGE",
            "Choose a finance range of up to 366 days.",
            status_code=422,
        )
    zone = ZoneInfo(timezone)
    start = datetime.combine(start_date, time.min, zone).astimezone(UTC)
    end = datetime.combine(end_date + timedelta(days=1), time.min, zone).astimezone(UTC)
    return start, end


def _audit(
    session: AsyncSession,
    context: StaffContext,
    event_type: str,
    entity_type: str,
    entity_id: uuid.UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditEvent(
            business_id=context.business_id,
            actor_auth_user_id=context.auth_user_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata or {},
        )
    )


async def _validate_expense_ownership(
    session: AsyncSession, context: StaffContext, request: ExpenseCreate
) -> None:
    if request.expense_date > datetime.now(ZoneInfo(context.timezone)).date():
        raise DomainError(
            "EXPENSE_DATE_IN_FUTURE",
            "Expense date cannot be in the future.",
            status_code=422,
        )
    checks = (
        (StaffProfile, request.paid_by_staff_id, "STAFF_NOT_FOUND"),
        (ScheduleResource, request.team_id, "TEAM_NOT_FOUND"),
        (Job, request.related_job_id, "JOB_NOT_FOUND"),
    )
    for model, value, code in checks:
        if value is None:
            continue
        found = await session.scalar(
            select(model.id).where(model.id == value, model.business_id == context.business_id)
        )
        if found is None:
            raise DomainError(
                code,
                "The selected expense reference was not found.",
                status_code=404,
            )


def _expense_view(row: Any) -> ExpenseView:
    expense, staff_name, team_name, booking_reference = row
    return ExpenseView(
        id=expense.id,
        expense_date=expense.expense_date,
        category=expense.category,
        description=expense.description,
        amount_minor=expense.amount_minor,
        currency_code=expense.currency_code,
        payment_method=expense.payment_method,
        paid_by_staff_id=expense.paid_by_staff_id,
        paid_by_staff_name=staff_name,
        team_id=expense.team_id,
        team_name=team_name,
        related_job_id=expense.related_job_id,
        related_booking_reference=booking_reference,
        supplier_name=expense.supplier_name,
        reference_number=expense.reference_number,
        notes=expense.notes,
        receipt_available=expense.receipt_object_path is not None,
        status=expense.status,
        created_by_staff_id=expense.created_by_staff_id,
        created_at=expense.created_at,
        voided_at=expense.voided_at,
        void_reason=expense.void_reason,
    )


def _expense_statement(context: StaffContext) -> Any:
    return (
        select(Expense, StaffProfile.display_name, ScheduleResource.name, Booking.reference)
        .select_from(Expense)
        .outerjoin(StaffProfile, StaffProfile.id == Expense.paid_by_staff_id)
        .outerjoin(ScheduleResource, ScheduleResource.id == Expense.team_id)
        .outerjoin(Job, Job.id == Expense.related_job_id)
        .outerjoin(Booking, Booking.id == Job.booking_id)
        .where(Expense.business_id == context.business_id)
    )


async def create_expense(
    session: AsyncSession, context: StaffContext, request: ExpenseCreate
) -> ExpenseView:
    duplicate = await session.scalar(
        select(Expense.id).where(
            Expense.business_id == context.business_id,
            Expense.client_event_id == request.client_event_id,
        )
    )
    if duplicate is not None:
        return await get_expense(session, context, duplicate)
    await _validate_expense_ownership(session, context, request)
    currency = (
        await session.scalar(
            select(BusinessSettings.currency_code).where(
                BusinessSettings.business_id == context.business_id
            )
        )
    ) or "AED"
    expense = Expense(
        business_id=context.business_id,
        expense_date=request.expense_date,
        category=request.category,
        description=request.description.strip(),
        amount_minor=request.amount_minor,
        currency_code=currency,
        payment_method=request.payment_method.strip().lower(),
        paid_by_staff_id=request.paid_by_staff_id,
        team_id=request.team_id,
        related_job_id=request.related_job_id,
        supplier_name=request.supplier_name,
        reference_number=request.reference_number,
        notes=request.notes,
        status="active",
        client_event_id=request.client_event_id,
        created_by_staff_id=context.staff_id,
    )
    session.add(expense)
    await session.flush()
    _audit(session, context, "expense_created", "expense", expense.id)
    return await get_expense(session, context, expense.id)


async def get_expense(
    session: AsyncSession, context: StaffContext, expense_id: uuid.UUID
) -> ExpenseView:
    row = (
        await session.execute(_expense_statement(context).where(Expense.id == expense_id).limit(1))
    ).one_or_none()
    if row is None:
        raise DomainError("EXPENSE_NOT_FOUND", "Expense not found.", status_code=404)
    return _expense_view(row)


async def list_expenses(
    session: AsyncSession,
    context: StaffContext,
    *,
    start_date: date,
    end_date: date,
    category: str | None = None,
    payment_method: str | None = None,
    staff_id: uuid.UUID | None = None,
    team_id: uuid.UUID | None = None,
    status: str | None = None,
    search: str | None = None,
    cursor: str | None = None,
    limit: int = 30,
) -> ExpenseList:
    _bounds(start_date, end_date, context.timezone)
    predicates = [
        Expense.business_id == context.business_id,
        Expense.expense_date >= start_date,
        Expense.expense_date <= end_date,
    ]
    aggregate_predicates = list(predicates)
    if category:
        predicates.append(Expense.category == category)
        aggregate_predicates.append(Expense.category == category)
    if payment_method:
        predicates.append(Expense.payment_method == payment_method)
        aggregate_predicates.append(Expense.payment_method == payment_method)
    if staff_id:
        predicates.append(Expense.paid_by_staff_id == staff_id)
        aggregate_predicates.append(Expense.paid_by_staff_id == staff_id)
    if team_id:
        predicates.append(Expense.team_id == team_id)
        aggregate_predicates.append(Expense.team_id == team_id)
    if status:
        predicates.append(Expense.status == status)
    if search:
        pattern = f"%{search.strip()}%"
        search_predicate = or_(
            Expense.description.ilike(pattern),
            Expense.supplier_name.ilike(pattern),
            Expense.reference_number.ilike(pattern),
        )
        predicates.append(search_predicate)
        aggregate_predicates.append(search_predicate)
    statement = _expense_statement(context).where(*predicates)
    if cursor:
        try:
            cursor_date_raw, cursor_id_raw = cursor.split("|", 1)
            cursor_date = date.fromisoformat(cursor_date_raw)
            cursor_id = uuid.UUID(cursor_id_raw)
        except ValueError as exc:
            raise DomainError(
                "INVALID_CURSOR", "Expense cursor is invalid.", status_code=422
            ) from exc
        statement = statement.where(
            or_(
                Expense.expense_date < cursor_date,
                and_(Expense.expense_date == cursor_date, Expense.id < cursor_id),
            )
        )
    rows = (
        await session.execute(
            statement.order_by(Expense.expense_date.desc(), Expense.id.desc()).limit(limit + 1)
        )
    ).all()
    more = len(rows) > limit
    selected = rows[:limit]
    aggregate_rows = (
        await session.execute(
            select(Expense.category, func.coalesce(func.sum(Expense.amount_minor), 0))
            .where(*aggregate_predicates, Expense.status == "active")
            .group_by(Expense.category)
        )
    ).all()
    total = sum(int(amount) for _category, amount in aggregate_rows)
    categories = [
        ExpenseCategoryTotal(
            category=item_category,
            amount_minor=amount,
            percentage=round(amount * 100 / total, 1) if total else 0,
        )
        for item_category, amount in aggregate_rows
    ]
    last = selected[-1][0] if selected else None
    return ExpenseList(
        items=[_expense_view(row) for row in selected],
        next_cursor=(f"{last.expense_date.isoformat()}|{last.id}" if more and last else None),
        total_expenses_minor=total,
        category_totals=categories,
        currency_code=selected[0][0].currency_code if selected else "AED",
    )


async def void_expense(
    session: AsyncSession,
    context: StaffContext,
    expense_id: uuid.UUID,
    reason: str,
) -> ExpenseView:
    expense = await session.scalar(
        select(Expense)
        .where(Expense.id == expense_id, Expense.business_id == context.business_id)
        .with_for_update()
    )
    if expense is None:
        raise DomainError("EXPENSE_NOT_FOUND", "Expense not found.", status_code=404)
    if expense.status == "voided":
        return await get_expense(session, context, expense.id)
    expense.status = "voided"
    expense.voided_at = datetime.now(UTC)
    expense.voided_by_staff_id = context.staff_id
    expense.void_reason = reason.strip()
    _audit(session, context, "expense_voided", "expense", expense.id, {"reason": reason.strip()})
    await session.flush()
    return await get_expense(session, context, expense.id)


def _pending_base(context: StaffContext) -> Any:
    reversal = aliased(PaymentTransaction)
    active_link = exists(
        select(CashReconciliationPayment.id).where(
            CashReconciliationPayment.payment_transaction_id == PaymentTransaction.id,
            CashReconciliationPayment.active.is_(True),
        )
    )
    reversed_payment = exists(
        select(reversal.id).where(
            reversal.payment_id == PaymentTransaction.payment_id,
            reversal.status == "succeeded",
            reversal.transaction_type.in_(("refund", "reversal", "void")),
        )
    )
    return (
        select(
            PaymentTransaction,
            Booking.reference,
            Job.id.label("job_id"),
            StaffProfile.display_name,
            Job.assigned_resource_id,
            ScheduleResource.name.label("team_name"),
            Payment.currency_code,
        )
        .select_from(PaymentTransaction)
        .join(Payment, Payment.id == PaymentTransaction.payment_id)
        .join(Booking, Booking.id == Payment.booking_id)
        .join(Job, Job.booking_id == Booking.id)
        .join(StaffProfile, StaffProfile.id == PaymentTransaction.actor_staff_id)
        .outerjoin(ScheduleResource, ScheduleResource.id == Job.assigned_resource_id)
        .where(
            Booking.business_id == context.business_id,
            PaymentTransaction.transaction_type == "cash_payment",
            PaymentTransaction.status == "succeeded",
            PaymentTransaction.actor_staff_id.is_not(None),
            ~active_link,
            ~reversed_payment,
        )
    )


async def pending_cash(
    session: AsyncSession, context: StaffContext, staff_id: uuid.UUID | None = None
) -> CashPendingList:
    statement = _pending_base(context)
    if staff_id:
        statement = statement.where(PaymentTransaction.actor_staff_id == staff_id)
    pending = statement.subquery()
    rows = (
        await session.execute(
            select(
                pending.c.actor_staff_id,
                pending.c.display_name,
                func.count(pending.c.id),
                func.sum(pending.c.amount_minor),
                func.max(pending.c.currency_code),
                func.min(pending.c.created_at),
            )
            .group_by(pending.c.actor_staff_id, pending.c.display_name)
            .order_by(func.sum(pending.c.amount_minor).desc())
        )
    ).all()
    return CashPendingList(
        items=[
            CashPendingStaff(
                staff_id=row_staff_id,
                staff_name=name,
                payment_count=count,
                expected_cash_minor=amount,
                currency_code=currency,
                oldest_unreconciled_at=oldest,
            )
            for row_staff_id, name, count, amount, currency, oldest in rows
        ]
    )


async def pending_cash_detail(
    session: AsyncSession, context: StaffContext, staff_id: uuid.UUID
) -> CashPendingDetail:
    rows = (
        await session.execute(
            _pending_base(context)
            .where(PaymentTransaction.actor_staff_id == staff_id)
            .order_by(PaymentTransaction.created_at, PaymentTransaction.id)
            .limit(200)
        )
    ).all()
    if not rows:
        staff_name = await session.scalar(
            select(StaffProfile.display_name).where(
                StaffProfile.id == staff_id,
                StaffProfile.business_id == context.business_id,
            )
        )
        if staff_name is None:
            raise DomainError("STAFF_NOT_FOUND", "Staff member not found.", status_code=404)
        return CashPendingDetail(
            staff_id=staff_id,
            staff_name=staff_name,
            expected_cash_minor=0,
            currency_code="AED",
            payments=[],
        )
    payments = [
        CashPendingPayment(
            payment_transaction_id=transaction.id,
            booking_reference=reference,
            job_id=job_id,
            amount_minor=transaction.amount_minor,
            currency_code=currency,
            collected_at=transaction.created_at,
        )
        for transaction, reference, job_id, _name, _team_id, _team_name, currency in rows
    ]
    return CashPendingDetail(
        staff_id=staff_id,
        staff_name=rows[0][3],
        expected_cash_minor=sum(item.amount_minor for item in payments),
        currency_code=payments[0].currency_code,
        payments=payments,
    )


async def _reconciliation_view(
    session: AsyncSession, context: StaffContext, reconciliation_id: uuid.UUID
) -> CashReconciliationView:
    row = (
        await session.execute(
            select(CashReconciliation, StaffProfile.display_name, ScheduleResource.name)
            .select_from(CashReconciliation)
            .join(StaffProfile, StaffProfile.id == CashReconciliation.staff_id)
            .outerjoin(ScheduleResource, ScheduleResource.id == CashReconciliation.team_id)
            .where(
                CashReconciliation.id == reconciliation_id,
                CashReconciliation.business_id == context.business_id,
            )
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        raise DomainError(
            "CASH_RECONCILIATION_NOT_FOUND",
            "Cash handover not found.",
            status_code=404,
        )
    reconciliation, staff_name, team_name = row
    payment_rows = (
        await session.execute(
            select(PaymentTransaction, Booking.reference, Job.id, Payment.currency_code)
            .join(
                CashReconciliationPayment,
                CashReconciliationPayment.payment_transaction_id == PaymentTransaction.id,
            )
            .join(Payment, Payment.id == PaymentTransaction.payment_id)
            .join(Booking, Booking.id == Payment.booking_id)
            .join(Job, Job.booking_id == Booking.id)
            .where(CashReconciliationPayment.reconciliation_id == reconciliation.id)
            .order_by(PaymentTransaction.created_at, PaymentTransaction.id)
        )
    ).all()
    payments = [
        CashPendingPayment(
            payment_transaction_id=transaction.id,
            booking_reference=reference,
            job_id=job_id,
            amount_minor=transaction.amount_minor,
            currency_code=currency,
            collected_at=transaction.created_at,
        )
        for transaction, reference, job_id, currency in payment_rows
    ]
    difference_label: Literal["exact", "short", "over"] = (
        "exact"
        if reconciliation.difference_minor == 0
        else "short"
        if reconciliation.difference_minor < 0
        else "over"
    )
    return CashReconciliationView(
        id=reconciliation.id,
        staff_id=reconciliation.staff_id,
        staff_name=staff_name,
        team_id=reconciliation.team_id,
        team_name=team_name,
        period_start=reconciliation.period_start,
        period_end=reconciliation.period_end,
        expected_cash_minor=reconciliation.expected_cash_minor,
        declared_cash_minor=reconciliation.declared_cash_minor,
        difference_minor=reconciliation.difference_minor,
        difference_label=difference_label,
        currency_code=reconciliation.currency_code,
        status=reconciliation.status,
        note=reconciliation.note,
        payment_count=len(payments),
        payments=payments,
        created_by_staff_id=reconciliation.created_by_staff_id,
        confirmed_at=reconciliation.confirmed_at,
        voided_at=reconciliation.voided_at,
        void_reason=reconciliation.void_reason,
    )


async def get_reconciliation(
    session: AsyncSession,
    context: StaffContext,
    reconciliation_id: uuid.UUID,
) -> CashReconciliationView:
    return await _reconciliation_view(session, context, reconciliation_id)


async def create_reconciliation(
    session: AsyncSession,
    context: StaffContext,
    request: CashReconciliationCreate,
) -> CashReconciliationView:
    duplicate = await session.scalar(
        select(CashReconciliation.id).where(
            CashReconciliation.business_id == context.business_id,
            CashReconciliation.client_event_id == request.client_event_id,
        )
    )
    if duplicate is not None:
        return await _reconciliation_view(session, context, duplicate)
    rows = (
        await session.execute(
            _pending_base(context)
            .where(
                PaymentTransaction.id.in_(request.payment_transaction_ids),
                PaymentTransaction.actor_staff_id == request.staff_id,
            )
            .order_by(PaymentTransaction.id)
            .with_for_update(of=PaymentTransaction)
        )
    ).all()
    if len(rows) != len(request.payment_transaction_ids):
        raise ConflictError(
            "CASH_RECONCILIATION_CONFLICT",
            "One or more cash payments are no longer available for handover.",
        )
    active_links = await session.scalar(
        select(func.count(CashReconciliationPayment.id)).where(
            CashReconciliationPayment.payment_transaction_id.in_(
                request.payment_transaction_ids
            ),
            CashReconciliationPayment.active.is_(True),
        )
    )
    if active_links:
        raise ConflictError(
            "CASH_RECONCILIATION_CONFLICT",
            "One or more cash payments were already handed over.",
        )
    expected = sum(row[0].amount_minor for row in rows)
    difference = request.declared_cash_minor - expected
    if difference and not request.note:
        raise DomainError(
            "CASH_DISCREPANCY_NOTE_REQUIRED",
            "Explain the cash difference before confirming handover.",
            status_code=422,
        )
    currencies = {row[6] for row in rows}
    if len(currencies) != 1:
        raise ConflictError(
            "CASH_RECONCILIATION_CURRENCY_MISMATCH",
            "Cash payments with different currencies cannot be combined.",
        )
    resource_ids = {row[4] for row in rows if row[4] is not None}
    team_id = next(iter(resource_ids)) if len(resource_ids) == 1 else None
    now = datetime.now(UTC)
    reconciliation = CashReconciliation(
        business_id=context.business_id,
        staff_id=request.staff_id,
        team_id=team_id,
        period_start=min(row[0].created_at for row in rows),
        period_end=max(row[0].created_at for row in rows),
        expected_cash_minor=expected,
        declared_cash_minor=request.declared_cash_minor,
        difference_minor=difference,
        currency_code=next(iter(currencies)),
        status="confirmed",
        note=request.note.strip() if request.note else None,
        client_event_id=request.client_event_id,
        created_by_staff_id=context.staff_id,
        confirmed_by_staff_id=context.staff_id,
        confirmed_at=now,
    )
    session.add(reconciliation)
    await session.flush()
    session.add_all(
        [
            CashReconciliationPayment(
                reconciliation_id=reconciliation.id,
                payment_transaction_id=row[0].id,
                active=True,
            )
            for row in rows
        ]
    )
    event = "cash_discrepancy_confirmed" if difference else "cash_reconciliation_confirmed"
    _audit(
        session,
        context,
        event,
        "cash_reconciliation",
        reconciliation.id,
        {"staff_id": str(request.staff_id), "difference_minor": difference},
    )
    await session.flush()
    return await _reconciliation_view(session, context, reconciliation.id)


async def list_reconciliations(
    session: AsyncSession,
    context: StaffContext,
    *,
    cursor: datetime | None = None,
    limit: int = 30,
) -> CashReconciliationList:
    payment_count = (
        select(func.count(CashReconciliationPayment.id))
        .where(CashReconciliationPayment.reconciliation_id == CashReconciliation.id)
        .correlate(CashReconciliation)
        .scalar_subquery()
    )
    statement = (
        select(
            CashReconciliation,
            StaffProfile.display_name,
            ScheduleResource.name,
            payment_count,
        )
        .select_from(CashReconciliation)
        .join(StaffProfile, StaffProfile.id == CashReconciliation.staff_id)
        .outerjoin(ScheduleResource, ScheduleResource.id == CashReconciliation.team_id)
        .where(CashReconciliation.business_id == context.business_id)
    )
    if cursor:
        statement = statement.where(CashReconciliation.confirmed_at < cursor)
    rows = (
        await session.execute(
            statement.order_by(CashReconciliation.confirmed_at.desc()).limit(limit + 1)
        )
    ).all()
    more = len(rows) > limit
    items = []
    for reconciliation, staff_name, team_name, count in rows[:limit]:
        label: Literal["exact", "short", "over"] = (
            "exact"
            if reconciliation.difference_minor == 0
            else "short"
            if reconciliation.difference_minor < 0
            else "over"
        )
        items.append(
            CashReconciliationView(
                id=reconciliation.id,
                staff_id=reconciliation.staff_id,
                staff_name=staff_name,
                team_id=reconciliation.team_id,
                team_name=team_name,
                period_start=reconciliation.period_start,
                period_end=reconciliation.period_end,
                expected_cash_minor=reconciliation.expected_cash_minor,
                declared_cash_minor=reconciliation.declared_cash_minor,
                difference_minor=reconciliation.difference_minor,
                difference_label=label,
                currency_code=reconciliation.currency_code,
                status=reconciliation.status,
                note=reconciliation.note,
                payment_count=count,
                payments=[],
                created_by_staff_id=reconciliation.created_by_staff_id,
                confirmed_at=reconciliation.confirmed_at,
                voided_at=reconciliation.voided_at,
                void_reason=reconciliation.void_reason,
            )
        )
    return CashReconciliationList(
        items=items,
        next_cursor=items[-1].confirmed_at.isoformat() if more and items else None,
    )


async def void_reconciliation(
    session: AsyncSession,
    context: StaffContext,
    reconciliation_id: uuid.UUID,
    reason: str,
) -> CashReconciliationView:
    reconciliation = await session.scalar(
        select(CashReconciliation)
        .where(
            CashReconciliation.id == reconciliation_id,
            CashReconciliation.business_id == context.business_id,
        )
        .with_for_update()
    )
    if reconciliation is None:
        raise DomainError(
            "CASH_RECONCILIATION_NOT_FOUND",
            "Cash handover not found.",
            status_code=404,
        )
    if reconciliation.status == "voided":
        return await _reconciliation_view(session, context, reconciliation.id)
    reconciliation.status = "voided"
    reconciliation.voided_at = datetime.now(UTC)
    reconciliation.voided_by_staff_id = context.staff_id
    reconciliation.void_reason = reason.strip()
    await session.execute(
        update(CashReconciliationPayment)
        .where(CashReconciliationPayment.reconciliation_id == reconciliation.id)
        .values(active=False)
    )
    _audit(
        session,
        context,
        "cash_reconciliation_voided",
        "cash_reconciliation",
        reconciliation.id,
        {"reason": reason.strip()},
    )
    await session.flush()
    return await _reconciliation_view(session, context, reconciliation.id)


async def finance_overview(
    session: AsyncSession,
    context: StaffContext,
    start_date: date,
    end_date: date,
) -> FinanceOverview:
    start, end = _bounds(start_date, end_date, context.timezone)
    pending_transactions = _pending_base(context).subquery()
    cash_pending_query = select(
        func.coalesce(func.sum(pending_transactions.c.amount_minor), 0)
    ).correlate(None).scalar_subquery()
    discrepancy_query = (
        select(func.coalesce(func.sum(CashReconciliation.difference_minor), 0))
        .where(
            CashReconciliation.business_id == context.business_id,
            CashReconciliation.status == "confirmed",
            CashReconciliation.confirmed_at >= start,
            CashReconciliation.confirmed_at < end,
        )
        .correlate(None)
        .scalar_subquery()
    )
    booked, outstanding, currency, cash_pending, discrepancy = (
        await session.execute(
            select(
                func.coalesce(func.sum(Booking.total_amount_minor), 0),
                func.coalesce(
                    func.sum(
                        case(
                            (Payment.status != "paid", Payment.amount_minor),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.max(Booking.currency_code),
                cash_pending_query,
                discrepancy_query,
            )
            .join(Payment, Payment.booking_id == Booking.id)
            .where(
                Booking.business_id == context.business_id,
                Booking.scheduled_start >= start,
                Booking.scheduled_start < end,
                Booking.status.in_(("confirmed", "cancellation_requested", "completed")),
            )
        )
    ).one()
    revenue_day = func.date(func.timezone(context.timezone, PaymentTransaction.created_at))
    signed_revenue = case(
        (
            PaymentTransaction.transaction_type.in_(("refund", "reversal", "void")),
            -PaymentTransaction.amount_minor,
        ),
        else_=PaymentTransaction.amount_minor,
    )
    revenue_rows = (
        await session.execute(
            select(
                revenue_day,
                Job.assigned_resource_id,
                ScheduleResource.name,
                func.coalesce(func.sum(signed_revenue), 0),
                func.count(func.distinct(Job.id)),
            )
            .select_from(PaymentTransaction)
            .join(Payment, Payment.id == PaymentTransaction.payment_id)
            .join(Booking, Booking.id == Payment.booking_id)
            .join(Job, Job.booking_id == Booking.id)
            .outerjoin(ScheduleResource, ScheduleResource.id == Job.assigned_resource_id)
            .where(
                Booking.business_id == context.business_id,
                PaymentTransaction.status == "succeeded",
                PaymentTransaction.created_at >= start,
                PaymentTransaction.created_at < end,
            )
            .group_by(revenue_day, Job.assigned_resource_id, ScheduleResource.name)
        )
    ).all()
    expense_rows = (
        await session.execute(
            select(
                Expense.expense_date,
                Expense.category,
                Expense.team_id,
                ScheduleResource.name,
                func.coalesce(func.sum(Expense.amount_minor), 0),
            )
            .outerjoin(ScheduleResource, ScheduleResource.id == Expense.team_id)
            .where(
                Expense.business_id == context.business_id,
                Expense.expense_date >= start_date,
                Expense.expense_date <= end_date,
                Expense.status == "active",
            )
            .group_by(
                Expense.expense_date,
                Expense.category,
                Expense.team_id,
                ScheduleResource.name,
            )
        )
    ).all()
    collected = sum(int(row[3]) for row in revenue_rows)
    expenses = sum(int(row[4]) for row in expense_rows)
    profit = collected - expenses
    category_amounts: dict[str, int] = {}
    day_revenue: dict[date, int] = {}
    day_expenses: dict[date, int] = {}
    team_revenue: dict[uuid.UUID, tuple[str, int, int]] = {}
    team_expenses: dict[uuid.UUID, tuple[str, int]] = {}
    for day, team_id, team_name, amount, jobs in revenue_rows:
        day_revenue[day] = day_revenue.get(day, 0) + int(amount)
        if team_id is not None:
            previous = team_revenue.get(team_id, (team_name or "Team", 0, 0))
            team_revenue[team_id] = (previous[0], previous[1] + int(amount), previous[2] + jobs)
    for day, category, team_id, team_name, amount in expense_rows:
        day_expenses[day] = day_expenses.get(day, 0) + int(amount)
        category_amounts[category] = category_amounts.get(category, 0) + int(amount)
        if team_id is not None:
            previous = team_expenses.get(team_id, (team_name or "Team", 0))
            team_expenses[team_id] = (previous[0], previous[1] + int(amount))
    days = sorted(set(day_revenue) | set(day_expenses))
    categories = [
        ExpenseCategoryTotal(
            category=item_category,
            amount_minor=amount,
            percentage=round(amount * 100 / expenses, 1) if expenses else 0,
        )
        for item_category, amount in sorted(
            category_amounts.items(), key=lambda item: item[1], reverse=True
        )
    ]
    team_ids = set(team_revenue) | set(team_expenses)
    teams = []
    for team_id in team_ids:
        revenue_name, revenue_amount, jobs = team_revenue.get(team_id, ("Team", 0, 0))
        expense_name, expense_amount = team_expenses.get(team_id, (revenue_name, 0))
        teams.append(
            TeamContribution(
                team_id=team_id,
                team_name=revenue_name if revenue_name != "Team" else expense_name,
                collected_revenue_minor=revenue_amount,
                completed_jobs=jobs,
                direct_expenses_minor=expense_amount,
                direct_contribution_minor=revenue_amount - expense_amount,
            )
        )
    return FinanceOverview(
        start_date=start_date,
        end_date=end_date,
        currency_code=currency or "AED",
        booked_sales_minor=int(booked),
        collected_revenue_minor=collected,
        outstanding_minor=int(outstanding),
        expenses_minor=expenses,
        operational_profit_minor=profit,
        margin_percent=round(profit * 100 / collected, 1) if collected else 0,
        cash_pending_minor=int(cash_pending or 0),
        cash_short_over_minor=int(discrepancy or 0),
        expense_categories=categories,
        series=[
            FinanceSeriesPoint(
                date=day,
                collected_revenue_minor=day_revenue.get(day, 0),
                expenses_minor=day_expenses.get(day, 0),
                operational_profit_minor=day_revenue.get(day, 0) - day_expenses.get(day, 0),
            )
            for day in days
        ],
        team_contributions=sorted(
            teams, key=lambda item: item.collected_revenue_minor, reverse=True
        ),
    )


async def personal_cash_summary(
    session: AsyncSession, context: StaffContext, target_date: date
) -> PersonalCashSummary:
    start, end = _bounds(target_date, target_date, context.timezone)
    collected = await session.scalar(
        select(func.coalesce(func.sum(PaymentTransaction.amount_minor), 0)).where(
            PaymentTransaction.actor_staff_id == context.staff_id,
            PaymentTransaction.transaction_type == "cash_payment",
            PaymentTransaction.status == "succeeded",
            PaymentTransaction.created_at >= start,
            PaymentTransaction.created_at < end,
        )
    )
    pending = await pending_cash(session, context, context.staff_id)
    currency = (
        await session.scalar(
            select(BusinessSettings.currency_code).where(
                BusinessSettings.business_id == context.business_id
            )
        )
    ) or "AED"
    return PersonalCashSummary(
        date=target_date,
        currency_code=pending.items[0].currency_code if pending.items else currency,
        collected_today_minor=int(collected or 0),
        awaiting_handover_minor=(pending.items[0].expected_cash_minor if pending.items else 0),
    )

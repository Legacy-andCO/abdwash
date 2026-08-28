import asyncio
import uuid
from datetime import date, datetime
from typing import Annotated, cast
from zoneinfo import ZoneInfo

import httpx
import structlog
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select

from app.auth.dependencies import ManagerContext, SessionDep, StaffContext, staff_context
from app.core.config import get_settings
from app.domain.enums import JobStatus
from app.domain.errors import DomainError
from app.integrations.eta import GoogleRoutesEtaProvider
from app.integrations.supabase_admin import SupabaseAdminClient
from app.integrations.supabase_storage import SupabaseStorageAdminClient
from app.models.entities import Booking, Job, JobPhoto
from app.schemas.catalogue import (
    AddonInput,
    AddonPatch,
    AddonView,
    BusinessBookingSettingsPatch,
    BusinessBookingSettingsView,
    CatalogueManagementView,
    ServiceInput,
    ServiceManagementView,
    ServicePatch,
)
from app.schemas.customer import (
    CustomerAddressResponse,
    CustomerAddressWrite,
    CustomerVehicleResponse,
    CustomerVehicleWrite,
    ManagerRescheduleCreate,
)
from app.schemas.finance import (
    CashPendingDetail,
    CashPendingList,
    CashReconciliationCreate,
    CashReconciliationList,
    CashReconciliationView,
    CashReconciliationVoid,
    ExpenseCreate,
    ExpenseList,
    ExpenseView,
    ExpenseVoid,
    FinanceOverview,
    PersonalCashSummary,
)
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemList,
    InventoryItemUpdate,
    InventoryItemView,
    InventoryLocationCreate,
    InventoryLocationUpdate,
    InventoryLocationView,
    InventoryMovementList,
    InventoryOperationView,
    InventoryOverview,
    InventoryReceiptCreate,
    InventoryStockCountCreate,
    InventoryThresholdUpdate,
    InventoryTransferCreate,
    InventoryUsageCreate,
    InventoryUsageReport,
    InventoryWastageCreate,
    ServiceConsumptionTemplateLine,
    ServiceConsumptionTemplateUpdate,
    StockLine,
    StockList,
    TeamStockSummary,
)
from app.schemas.loyalty import (
    LoyaltyAdjustment,
    LoyaltySettingsUpdate,
    LoyaltySettingsView,
    LoyaltySummary,
)
from app.schemas.manager_customers import (
    ManagerCustomerDetail,
    ManagerCustomerList,
    ManagerCustomerUpdate,
)
from app.schemas.staff import (
    AssignmentAction,
    AttendanceAction,
    AttendanceList,
    AttendanceOverviewItem,
    AttendanceRecord,
    CancellationItem,
    CancellationReview,
    CashPaymentResult,
    CashTenderAction,
    JobAction,
    JobChecklistUpdate,
    JobComplaintCreate,
    JobComplaintReview,
    JobInspectionInput,
    JobPhotoCreate,
    JobPhotoUploadGrant,
    JobPhotoView,
    JobQualityIssueCreate,
    JobQualityView,
    LeaveCreate,
    LeaveReview,
    LeaveView,
    OperationsDashboard,
    OwnProfileUpdate,
    ReportSummary,
    ReportV2,
    ShiftAssignmentCreate,
    ShiftAssignmentView,
    ShiftCreate,
    ShiftView,
    StaffAccountCreate,
    StaffAccountUpdate,
    StaffJob,
    StaffJobList,
    StaffMember,
    StaffPasswordReset,
    StaffPasswordResetResult,
    StaffProfileView,
    StartTripAction,
    SyncState,
    TeamCreate,
    TeamDetail,
    TeamMembersUpdate,
    TeamSummary,
    TeamUpdate,
    TemporaryPasswordUpdate,
)
from app.services.customers import reschedule_managed_booking
from app.services.finance import (
    create_expense,
    create_reconciliation,
    finance_overview,
    get_expense,
    get_reconciliation,
    list_expenses,
    list_reconciliations,
    pending_cash,
    pending_cash_detail,
    personal_cash_summary,
    void_expense,
    void_reconciliation,
)
from app.services.inventory import (
    create_item,
    create_location,
    get_item,
    get_service_template,
    inventory_overview,
    list_items,
    list_locations,
    list_movements,
    list_stock,
    receive_stock,
    record_stock_count,
    record_usage,
    record_wastage,
    team_stock_summary,
    transfer_stock,
    update_item,
    update_location,
    update_service_template,
    update_threshold,
    usage_report,
)
from app.services.job_quality import (
    add_issue,
    confirm_photo,
    create_complaint,
    get_job_quality,
    load_pending_photo,
    prepare_photo_upload,
    review_complaint,
    save_inspection,
    update_checklist,
)
from app.services.loyalty import (
    adjust_loyalty,
    get_loyalty_settings,
    update_loyalty_settings,
)
from app.services.manager_customers import (
    create_manager_address,
    create_manager_vehicle,
    deactivate_manager_vehicle,
    delete_manager_address,
    list_manager_customers,
    manager_customer_detail,
    update_manager_address,
    update_manager_customer,
    update_manager_vehicle,
)
from app.services.service_catalogue import (
    create_addon,
    create_service,
    get_business_booking_settings,
    list_managed_catalogue,
    update_addon,
    update_business_booking_settings,
    update_service,
)
from app.services.staff_accounts import (
    create_staff_account,
    get_own_profile,
    list_staff_accounts,
    reset_staff_password,
    reset_staff_password_choice,
    update_own_profile,
    update_staff_account,
)
from app.services.staff_operations import (
    assign_job,
    get_job,
    list_cancellations,
    list_jobs,
    list_team,
    record_cash,
    report_summary,
    review_cancellation,
    start_trip,
    transition_job,
)
from app.services.sync_state import bump_sync_revisions, get_sync_state
from app.services.workforce import (
    assign_shift,
    attendance_overview,
    clock_in,
    clock_out,
    create_leave,
    create_shift,
    create_team,
    get_team,
    list_attendance,
    list_leave,
    list_shift_assignments,
    list_shifts,
    list_teams,
    operations_dashboard,
    replace_team_members,
    report_v2,
    review_leave,
    update_team,
)

router = APIRouter(prefix="/api/v1/staff", tags=["staff"])
logger = structlog.get_logger()
StaffDep = Annotated[StaffContext, Depends(staff_context)]


@router.get("/catalogue", response_model=CatalogueManagementView)
async def managed_catalogue(session: SessionDep, context: StaffDep) -> CatalogueManagementView:
    return await list_managed_catalogue(session, context)


@router.post("/catalogue/services", response_model=ServiceManagementView, status_code=201)
async def managed_service_create(
    payload: ServiceInput, session: SessionDep, context: ManagerContext
) -> ServiceManagementView:
    async with session.begin():
        result = await create_service(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "schedule")
        return result


@router.patch("/catalogue/services/{service_id}", response_model=ServiceManagementView)
async def managed_service_update(
    service_id: uuid.UUID,
    payload: ServicePatch,
    session: SessionDep,
    context: ManagerContext,
) -> ServiceManagementView:
    async with session.begin():
        result = await update_service(session, context, service_id, payload)
        await bump_sync_revisions(session, context.business_id, "schedule")
        return result


@router.post("/catalogue/services/{service_id}/addons", response_model=AddonView, status_code=201)
async def managed_addon_create(
    service_id: uuid.UUID,
    payload: AddonInput,
    session: SessionDep,
    context: ManagerContext,
) -> AddonView:
    async with session.begin():
        result = await create_addon(session, context, service_id, payload)
        await bump_sync_revisions(session, context.business_id, "schedule")
        return result


@router.patch("/catalogue/addons/{addon_id}", response_model=AddonView)
async def managed_addon_update(
    addon_id: uuid.UUID,
    payload: AddonPatch,
    session: SessionDep,
    context: ManagerContext,
) -> AddonView:
    async with session.begin():
        result = await update_addon(session, context, addon_id, payload)
        await bump_sync_revisions(session, context.business_id, "schedule")
        return result


@router.get("/business-settings", response_model=BusinessBookingSettingsView)
async def business_booking_settings(
    session: SessionDep, context: StaffDep
) -> BusinessBookingSettingsView:
    return await get_business_booking_settings(session, context)


@router.patch("/business-settings", response_model=BusinessBookingSettingsView)
async def business_booking_settings_update(
    payload: BusinessBookingSettingsPatch,
    session: SessionDep,
    context: ManagerContext,
) -> BusinessBookingSettingsView:
    async with session.begin():
        result = await update_business_booking_settings(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "schedule")
        return result


def _photo_storage(request: Request) -> SupabaseStorageAdminClient:
    settings = get_settings()
    return SupabaseStorageAdminClient(
        cast(httpx.AsyncClient, request.app.state.http_client),
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
        bucket=settings.job_photo_bucket,
    )


@router.get("/context")
async def context(
    value: Annotated[StaffContext, Depends(staff_context)],
) -> dict[str, str | bool | None]:
    return {
        "staff_id": str(value.staff_id),
        "business_id": str(value.business_id),
        "business_name": value.business_name,
        "role": value.role,
        "timezone": value.timezone,
        "display_name": value.display_name,
        "username": value.username,
        "phone": value.phone,
        "must_change_password": value.must_change_password,
    }


@router.get("/sync-state", response_model=SyncState)
async def sync_state(session: SessionDep, context: StaffDep) -> SyncState:
    return await get_sync_state(session, context.business_id)


def _admin(request: Request) -> SupabaseAdminClient:
    settings = get_settings()
    return SupabaseAdminClient(
        cast(httpx.AsyncClient, request.app.state.http_client),
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
    )


@router.get("/profile", response_model=StaffProfileView)
async def own_profile(session: SessionDep, context: StaffDep) -> StaffProfileView:
    return await get_own_profile(session, context)


@router.patch("/profile", response_model=StaffProfileView)
async def own_profile_update(
    payload: OwnProfileUpdate,
    request: Request,
    session: SessionDep,
    context: StaffDep,
) -> StaffProfileView:
    return await update_own_profile(
        session,
        context,
        payload,
        _admin(request) if payload.password is not None else None,
    )


@router.get("/users", response_model=list[StaffProfileView])
async def staff_users(session: SessionDep, context: ManagerContext) -> list[StaffProfileView]:
    return await list_staff_accounts(session, context)


@router.post("/users", response_model=StaffProfileView, status_code=201)
async def staff_user_create(
    payload: StaffAccountCreate,
    request: Request,
    session: SessionDep,
    context: ManagerContext,
) -> StaffProfileView:
    return await create_staff_account(session, context, payload, _admin(request))


@router.patch("/users/{staff_id}", response_model=StaffProfileView)
async def staff_user_update(
    staff_id: uuid.UUID,
    payload: StaffAccountUpdate,
    session: SessionDep,
    context: ManagerContext,
) -> StaffProfileView:
    async with session.begin():
        result = await update_staff_account(session, context, staff_id, payload)
        await bump_sync_revisions(session, context.business_id, "workforce")
        return result


@router.post("/users/{staff_id}/temporary-password", status_code=204)
async def staff_user_password(
    staff_id: uuid.UUID,
    payload: TemporaryPasswordUpdate,
    request: Request,
    session: SessionDep,
    context: ManagerContext,
) -> None:
    await reset_staff_password(
        session, context, staff_id, payload.temporary_password, _admin(request)
    )


@router.post("/users/{staff_id}/password", response_model=StaffPasswordResetResult)
async def staff_user_password_reset(
    staff_id: uuid.UUID,
    payload: StaffPasswordReset,
    request: Request,
    session: SessionDep,
    context: ManagerContext,
) -> StaffPasswordResetResult:
    return await reset_staff_password_choice(
        session,
        context,
        staff_id,
        mode=payload.mode,
        new_password=payload.new_password,
        admin=_admin(request),
    )


@router.get("/teams", response_model=list[TeamSummary])
async def teams(session: SessionDep, context: StaffDep) -> list[TeamSummary]:
    return await list_teams(session, context)


@router.post("/teams", response_model=TeamDetail, status_code=201)
async def team_create(
    payload: TeamCreate, session: SessionDep, context: ManagerContext
) -> TeamDetail:
    async with session.begin():
        result = await create_team(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "workforce", "schedule")
        return result


@router.get("/teams/{team_id}", response_model=TeamDetail)
async def team_get(team_id: uuid.UUID, session: SessionDep, context: StaffDep) -> TeamDetail:
    return await get_team(session, context, team_id)


@router.patch("/teams/{team_id}", response_model=TeamDetail)
async def team_update(
    team_id: uuid.UUID,
    payload: TeamUpdate,
    session: SessionDep,
    context: ManagerContext,
) -> TeamDetail:
    async with session.begin():
        result = await update_team(session, context, team_id, payload)
        await bump_sync_revisions(session, context.business_id, "workforce", "schedule")
        return result


@router.put("/teams/{team_id}/members", response_model=TeamDetail)
async def team_members(
    team_id: uuid.UUID,
    payload: TeamMembersUpdate,
    session: SessionDep,
    context: ManagerContext,
) -> TeamDetail:
    async with session.begin():
        result = await replace_team_members(session, context, team_id, payload)
        await bump_sync_revisions(session, context.business_id, "workforce")
        return result


@router.get("/attendance", response_model=AttendanceList)
async def attendance(
    session: SessionDep,
    context: StaffDep,
    start_date: date,
    end_date: date,
    staff_id: uuid.UUID | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> AttendanceList:
    return await list_attendance(
        session,
        context,
        start_date=start_date,
        end_date=end_date,
        staff_id=staff_id,
        offset=offset,
        limit=limit,
    )


@router.get("/attendance/overview", response_model=list[AttendanceOverviewItem])
async def attendance_status_overview(
    session: SessionDep,
    context: StaffDep,
    day: date | None = None,
) -> list[AttendanceOverviewItem]:
    target = day or datetime.now(ZoneInfo(context.timezone)).date()
    return await attendance_overview(session, context, day=target)


@router.post("/attendance/clock-in", response_model=AttendanceRecord)
async def attendance_clock_in(
    payload: AttendanceAction, session: SessionDep, context: StaffDep
) -> AttendanceRecord:
    async with session.begin():
        result = await clock_in(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "workforce")
        return result


@router.post("/attendance/clock-out", response_model=AttendanceRecord)
async def attendance_clock_out(
    payload: AttendanceAction, session: SessionDep, context: StaffDep
) -> AttendanceRecord:
    async with session.begin():
        result = await clock_out(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "workforce")
        return result


@router.get("/shifts", response_model=list[ShiftView])
async def shifts(session: SessionDep, context: StaffDep) -> list[ShiftView]:
    return await list_shifts(session, context)


@router.post("/shifts", response_model=ShiftView, status_code=201)
async def shift_create(
    payload: ShiftCreate, session: SessionDep, context: ManagerContext
) -> ShiftView:
    async with session.begin():
        result = await create_shift(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "workforce")
        return result


@router.get("/shift-assignments", response_model=list[ShiftAssignmentView])
async def shift_assignments(
    start_date: date,
    end_date: date,
    session: SessionDep,
    context: StaffDep,
) -> list[ShiftAssignmentView]:
    return await list_shift_assignments(session, context, start_date=start_date, end_date=end_date)


@router.put("/shift-assignments", response_model=ShiftAssignmentView)
async def shift_assignment(
    payload: ShiftAssignmentCreate,
    session: SessionDep,
    context: ManagerContext,
) -> ShiftAssignmentView:
    async with session.begin():
        result = await assign_shift(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "workforce")
        return result


@router.get("/leave", response_model=list[LeaveView])
async def leave(
    session: SessionDep, context: StaffDep, status: str | None = None
) -> list[LeaveView]:
    return await list_leave(session, context, status=status)


@router.post("/leave", response_model=LeaveView, status_code=201)
async def leave_create(payload: LeaveCreate, session: SessionDep, context: StaffDep) -> LeaveView:
    async with session.begin():
        result = await create_leave(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "workforce")
        return result


@router.post("/leave/{leave_id}/review", response_model=LeaveView)
async def leave_review(
    leave_id: uuid.UUID,
    payload: LeaveReview,
    session: SessionDep,
    context: ManagerContext,
) -> LeaveView:
    async with session.begin():
        result = await review_leave(session, context, leave_id, payload)
        await bump_sync_revisions(session, context.business_id, "workforce")
        return result


@router.get("/dashboard", response_model=OperationsDashboard)
async def dashboard(
    session: SessionDep,
    context: ManagerContext,
    day: date | None = None,
) -> OperationsDashboard:
    target = day or datetime.now(ZoneInfo(context.timezone)).date()
    return await operations_dashboard(session, context, day=target)


@router.get("/reports/v2", response_model=ReportV2)
async def reports_v2(
    start_date: date,
    end_date: date,
    session: SessionDep,
    context: ManagerContext,
) -> ReportV2:
    return await report_v2(session, context, start_date, end_date)


@router.get("/finance/overview", response_model=FinanceOverview)
async def finance_overview_view(
    start_date: date,
    end_date: date,
    session: SessionDep,
    context: ManagerContext,
) -> FinanceOverview:
    return await finance_overview(session, context, start_date, end_date)


@router.get("/finance/expenses", response_model=ExpenseList)
async def finance_expenses(
    start_date: date,
    end_date: date,
    session: SessionDep,
    context: ManagerContext,
    category: str | None = None,
    payment_method: str | None = None,
    staff_id: uuid.UUID | None = None,
    team_id: uuid.UUID | None = None,
    status: Annotated[str | None, Query(pattern="^(active|voided)$")] = None,
    search: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ExpenseList:
    return await list_expenses(
        session,
        context,
        start_date=start_date,
        end_date=end_date,
        category=category,
        payment_method=payment_method,
        staff_id=staff_id,
        team_id=team_id,
        status=status,
        search=search,
        cursor=cursor,
        limit=limit,
    )


@router.post("/finance/expenses", response_model=ExpenseView, status_code=201)
async def finance_expense_create(
    payload: ExpenseCreate,
    session: SessionDep,
    context: ManagerContext,
) -> ExpenseView:
    async with session.begin():
        result = await create_expense(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "finance")
        return result


@router.get("/finance/expenses/{expense_id}", response_model=ExpenseView)
async def finance_expense_detail(
    expense_id: uuid.UUID,
    session: SessionDep,
    context: ManagerContext,
) -> ExpenseView:
    return await get_expense(session, context, expense_id)


@router.post("/finance/expenses/{expense_id}/void", response_model=ExpenseView)
async def finance_expense_void(
    expense_id: uuid.UUID,
    payload: ExpenseVoid,
    session: SessionDep,
    context: ManagerContext,
) -> ExpenseView:
    async with session.begin():
        result = await void_expense(session, context, expense_id, payload.reason)
        await bump_sync_revisions(session, context.business_id, "finance")
        return result


@router.get("/finance/cash/pending", response_model=CashPendingList)
async def finance_cash_pending(
    session: SessionDep,
    context: ManagerContext,
    staff_id: uuid.UUID | None = None,
) -> CashPendingList:
    return await pending_cash(session, context, staff_id)


@router.get("/finance/cash/pending/{staff_id}", response_model=CashPendingDetail)
async def finance_cash_pending_detail(
    staff_id: uuid.UUID,
    session: SessionDep,
    context: ManagerContext,
) -> CashPendingDetail:
    return await pending_cash_detail(session, context, staff_id)


@router.get("/finance/cash/reconciliations", response_model=CashReconciliationList)
async def finance_cash_reconciliations(
    session: SessionDep,
    context: ManagerContext,
    cursor: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> CashReconciliationList:
    return await list_reconciliations(session, context, cursor=cursor, limit=limit)


@router.post(
    "/finance/cash/reconciliations",
    response_model=CashReconciliationView,
    status_code=201,
)
async def finance_cash_reconciliation_create(
    payload: CashReconciliationCreate,
    session: SessionDep,
    context: ManagerContext,
) -> CashReconciliationView:
    async with session.begin():
        result = await create_reconciliation(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "finance")
        return result


@router.get(
    "/finance/cash/reconciliations/{reconciliation_id}",
    response_model=CashReconciliationView,
)
async def finance_cash_reconciliation_detail(
    reconciliation_id: uuid.UUID,
    session: SessionDep,
    context: ManagerContext,
) -> CashReconciliationView:
    return await get_reconciliation(session, context, reconciliation_id)


@router.post(
    "/finance/cash/reconciliations/{reconciliation_id}/void",
    response_model=CashReconciliationView,
)
async def finance_cash_reconciliation_void(
    reconciliation_id: uuid.UUID,
    payload: CashReconciliationVoid,
    session: SessionDep,
    context: ManagerContext,
) -> CashReconciliationView:
    async with session.begin():
        result = await void_reconciliation(session, context, reconciliation_id, payload.reason)
        await bump_sync_revisions(session, context.business_id, "finance")
        return result


@router.get("/finance/cash/mine", response_model=PersonalCashSummary)
async def finance_my_cash(
    session: SessionDep,
    context: StaffDep,
    day: date | None = None,
) -> PersonalCashSummary:
    target = day or datetime.now(ZoneInfo(context.timezone)).date()
    return await personal_cash_summary(session, context, target)


@router.get("/inventory/overview", response_model=InventoryOverview)
async def inventory_overview_view(
    session: SessionDep, context: ManagerContext
) -> InventoryOverview:
    return await inventory_overview(session, context)


@router.get("/inventory/items", response_model=InventoryItemList)
async def inventory_items(
    session: SessionDep,
    context: StaffDep,
    search: str | None = None,
    category: str | None = None,
    active: bool | None = True,
    include_inactive: bool = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> InventoryItemList:
    return await list_items(
        session,
        context,
        search=search,
        category=category,
        active=None if include_inactive else active,
        offset=offset,
        limit=limit,
    )


@router.post("/inventory/items", response_model=InventoryItemView, status_code=201)
async def inventory_item_create(
    payload: InventoryItemCreate, session: SessionDep, context: ManagerContext
) -> InventoryItemView:
    async with session.begin():
        result = await create_item(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "inventory")
        return result


@router.get("/inventory/items/{item_id}", response_model=InventoryItemView)
async def inventory_item_detail(
    item_id: uuid.UUID, session: SessionDep, context: StaffDep
) -> InventoryItemView:
    return await get_item(session, context, item_id)


@router.patch("/inventory/items/{item_id}", response_model=InventoryItemView)
async def inventory_item_update(
    item_id: uuid.UUID,
    payload: InventoryItemUpdate,
    session: SessionDep,
    context: ManagerContext,
) -> InventoryItemView:
    async with session.begin():
        result = await update_item(session, context, item_id, payload)
        await bump_sync_revisions(session, context.business_id, "inventory")
        return result


@router.get("/inventory/locations", response_model=list[InventoryLocationView])
async def inventory_locations(
    session: SessionDep, context: StaffDep, active: bool | None = True
) -> list[InventoryLocationView]:
    return await list_locations(session, context, active=active)


@router.post("/inventory/locations", response_model=InventoryLocationView, status_code=201)
async def inventory_location_create(
    payload: InventoryLocationCreate, session: SessionDep, context: ManagerContext
) -> InventoryLocationView:
    async with session.begin():
        result = await create_location(session, context, payload)
        await bump_sync_revisions(session, context.business_id, "inventory")
        return result


@router.patch("/inventory/locations/{location_id}", response_model=InventoryLocationView)
async def inventory_location_update(
    location_id: uuid.UUID,
    payload: InventoryLocationUpdate,
    session: SessionDep,
    context: ManagerContext,
) -> InventoryLocationView:
    async with session.begin():
        result = await update_location(session, context, location_id, payload)
        await bump_sync_revisions(session, context.business_id, "inventory")
        return result


@router.get("/inventory/stock", response_model=StockList)
async def inventory_stock(
    session: SessionDep,
    context: StaffDep,
    location_id: uuid.UUID | None = None,
    search: str | None = None,
    category: str | None = None,
    status: Annotated[str | None, Query(pattern="^(normal|low|out)$")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> StockList:
    return await list_stock(
        session,
        context,
        location_id=location_id,
        search=search,
        category=category,
        status=status,
        offset=offset,
        limit=limit,
    )


@router.patch(
    "/inventory/locations/{location_id}/items/{item_id}/threshold",
    response_model=StockLine,
)
async def inventory_threshold_update(
    location_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: InventoryThresholdUpdate,
    session: SessionDep,
    context: ManagerContext,
) -> StockLine:
    async with session.begin():
        result = await update_threshold(session, context, location_id, item_id, payload)
        await bump_sync_revisions(session, context.business_id, "inventory")
        return result


@router.post("/inventory/receipts", response_model=InventoryOperationView, status_code=201)
async def inventory_receive(
    payload: InventoryReceiptCreate, session: SessionDep, context: ManagerContext
) -> InventoryOperationView:
    async with session.begin():
        result, created, finance_created = await receive_stock(session, context, payload)
        if created:
            await bump_sync_revisions(session, context.business_id, "inventory")
        if finance_created:
            await bump_sync_revisions(session, context.business_id, "finance")
        return result


@router.post("/inventory/transfers", response_model=InventoryOperationView, status_code=201)
async def inventory_transfer(
    payload: InventoryTransferCreate, session: SessionDep, context: ManagerContext
) -> InventoryOperationView:
    async with session.begin():
        result, created = await transfer_stock(session, context, payload)
        if created:
            await bump_sync_revisions(session, context.business_id, "inventory")
        return result


@router.post("/inventory/usage", response_model=InventoryOperationView, status_code=201)
async def inventory_usage(
    payload: InventoryUsageCreate, session: SessionDep, context: StaffDep
) -> InventoryOperationView:
    async with session.begin():
        result, created = await record_usage(session, context, payload)
        if created:
            await bump_sync_revisions(session, context.business_id, "inventory")
        return result


@router.post("/inventory/wastage", response_model=InventoryOperationView, status_code=201)
async def inventory_wastage(
    payload: InventoryWastageCreate, session: SessionDep, context: ManagerContext
) -> InventoryOperationView:
    async with session.begin():
        result, created = await record_wastage(session, context, payload)
        if created:
            await bump_sync_revisions(session, context.business_id, "inventory")
        return result


@router.post("/inventory/stock-counts", response_model=InventoryOperationView, status_code=201)
async def inventory_stock_count(
    payload: InventoryStockCountCreate, session: SessionDep, context: ManagerContext
) -> InventoryOperationView:
    async with session.begin():
        result, created = await record_stock_count(session, context, payload)
        if created:
            await bump_sync_revisions(session, context.business_id, "inventory")
        return result


@router.get("/inventory/movements", response_model=InventoryMovementList)
async def inventory_movements(
    session: SessionDep,
    context: StaffDep,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    item_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    movement_type: str | None = None,
    team_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> InventoryMovementList:
    return await list_movements(
        session,
        context,
        start_at=start_at,
        end_at=end_at,
        item_id=item_id,
        location_id=location_id,
        movement_type=movement_type,
        team_id=team_id,
        job_id=job_id,
        actor_id=actor_id,
        offset=offset,
        limit=limit,
    )


@router.get("/inventory/reports/usage", response_model=InventoryUsageReport)
async def inventory_usage_report(
    start_at: datetime,
    end_at: datetime,
    session: SessionDep,
    context: ManagerContext,
) -> InventoryUsageReport:
    return await usage_report(session, context, start_at, end_at)


@router.get("/inventory/teams/{team_id}/summary", response_model=TeamStockSummary)
async def inventory_team_summary(
    team_id: uuid.UUID, session: SessionDep, context: StaffDep
) -> TeamStockSummary:
    return await team_stock_summary(session, context, team_id)


@router.get(
    "/inventory/services/{service_id}/template",
    response_model=list[ServiceConsumptionTemplateLine],
)
async def inventory_service_template(
    service_id: uuid.UUID, session: SessionDep, context: StaffDep
) -> list[ServiceConsumptionTemplateLine]:
    return await get_service_template(session, context, service_id)


@router.put(
    "/inventory/services/{service_id}/template",
    response_model=list[ServiceConsumptionTemplateLine],
)
async def inventory_service_template_update(
    service_id: uuid.UUID,
    payload: ServiceConsumptionTemplateUpdate,
    session: SessionDep,
    context: ManagerContext,
) -> list[ServiceConsumptionTemplateLine]:
    async with session.begin():
        result = await update_service_template(session, context, service_id, payload)
        await bump_sync_revisions(session, context.business_id, "inventory")
        return result


@router.get("/management-check")
async def management_check(value: ManagerContext) -> dict[str, str]:
    return {"status": "authorized", "role": value.role}


@router.get("/jobs", response_model=StaffJobList)
async def jobs(
    session: SessionDep,
    context: Annotated[StaffContext, Depends(staff_context)],
    day: Annotated[date | None, Query(alias="date")] = None,
    start_date: date | None = None,
    end_date: date | None = None,
    view: Annotated[str | None, Query(pattern="^(today|upcoming|history|unassigned|all)$")] = None,
    status: str | None = None,
    scope: Annotated[str, Query(pattern="^(my|all)$")] = "my",
    team_id: uuid.UUID | None = None,
    employee_id: uuid.UUID | None = None,
    payment_method: str | None = None,
    service_id: uuid.UUID | None = None,
    search: str | None = Query(default=None, min_length=1, max_length=160),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> StaffJobList:
    return await list_jobs(
        session,
        context,
        day=day,
        start_date=start_date,
        end_date=end_date,
        view=view,
        status=status,
        scope=scope,
        team_id=team_id,
        staff_id=employee_id,
        payment_method=payment_method,
        service_id=service_id,
        search=search,
        offset=offset,
        limit=limit,
    )


@router.get("/jobs/{job_id}", response_model=StaffJob)
async def job_detail(
    job_id: uuid.UUID, session: SessionDep, context: Annotated[StaffContext, Depends(staff_context)]
) -> StaffJob:
    return await get_job(session, context, job_id)


@router.get("/jobs/{job_id}/quality", response_model=JobQualityView)
async def job_quality_detail(
    job_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    context: StaffDep,
) -> JobQualityView:
    async with session.begin():
        result = await get_job_quality(session, context, job_id)
        path_rows = (
            await session.execute(
                select(JobPhoto.id, JobPhoto.storage_path).where(
                    JobPhoto.id.in_([photo.id for photo in result.photos]),
                    JobPhoto.business_id == context.business_id,
                )
            )
        ).all()
        photo_paths: dict[uuid.UUID, str] = {row[0]: row[1] for row in path_rows}
    if not photo_paths:
        return result
    settings = get_settings()
    storage = _photo_storage(request)

    async def signed_access(photo_id: uuid.UUID, path: str) -> tuple[uuid.UUID, str | None]:
        try:
            return (
                photo_id,
                await storage.create_signed_download(path, settings.job_photo_signed_url_seconds),
            )
        except (DomainError, httpx.HTTPError):
            logger.warning("job_photo_access_grant_failed", photo_id=str(photo_id))
            return photo_id, None

    signed = await asyncio.gather(
        *(signed_access(photo_id, path) for photo_id, path in photo_paths.items())
    )
    access_urls = dict(signed)
    return result.model_copy(
        update={
            "photos": [
                photo.model_copy(update={"access_url": access_urls.get(photo.id)})
                for photo in result.photos
            ]
        }
    )


@router.put("/jobs/{job_id}/quality/inspection", status_code=204)
async def job_quality_inspection(
    job_id: uuid.UUID,
    payload: JobInspectionInput,
    session: SessionDep,
    context: StaffDep,
) -> None:
    async with session.begin():
        await save_inspection(session, context, job_id, payload)
        await bump_sync_revisions(session, context.business_id, "jobs")


@router.put("/jobs/{job_id}/quality/checklist", status_code=204)
async def job_quality_checklist(
    job_id: uuid.UUID,
    payload: JobChecklistUpdate,
    session: SessionDep,
    context: StaffDep,
) -> None:
    async with session.begin():
        await update_checklist(session, context, job_id, payload)
        await bump_sync_revisions(session, context.business_id, "jobs")


@router.post("/jobs/{job_id}/quality/issues", status_code=201)
async def job_quality_issue(
    job_id: uuid.UUID,
    payload: JobQualityIssueCreate,
    session: SessionDep,
    context: StaffDep,
) -> None:
    async with session.begin():
        await add_issue(session, context, job_id, payload)
        await bump_sync_revisions(session, context.business_id, "jobs")


@router.post(
    "/jobs/{job_id}/quality/photos/upload",
    response_model=JobPhotoUploadGrant,
    status_code=201,
)
async def job_quality_photo_upload(
    job_id: uuid.UUID,
    payload: JobPhotoCreate,
    request: Request,
    session: SessionDep,
    context: StaffDep,
) -> JobPhotoUploadGrant:
    async with session.begin():
        photo = await prepare_photo_upload(session, context, job_id, payload)
    settings = get_settings()
    token = await _photo_storage(request).create_signed_upload(photo.storage_path)
    return JobPhotoUploadGrant(
        photo=JobPhotoView(
            id=photo.id,
            category=photo.category,
            caption=photo.caption,
            status=photo.status,
            created_by_staff_id=photo.created_by_staff_id,
            created_by_staff_name=context.display_name,
            created_at=photo.created_at,
        ),
        bucket=settings.job_photo_bucket,
        path=photo.storage_path,
        upload_token=token,
        max_bytes=settings.job_photo_max_bytes,
    )


@router.post("/jobs/{job_id}/quality/photos/{photo_id}/complete", status_code=204)
async def job_quality_photo_complete(
    job_id: uuid.UUID,
    photo_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    context: StaffDep,
) -> None:
    photo = await load_pending_photo(session, context, job_id, photo_id)
    photo_path = photo.storage_path
    await session.rollback()
    storage = _photo_storage(request)
    object_info = await storage.object_info(photo_path)
    async with session.begin():
        await confirm_photo(
            session,
            context,
            job_id,
            photo_id,
            object_info=object_info,
            max_bytes=get_settings().job_photo_max_bytes,
        )
        await bump_sync_revisions(session, context.business_id, "jobs")


@router.post("/jobs/{job_id}/quality/complaints", status_code=201)
async def job_quality_complaint(
    job_id: uuid.UUID,
    payload: JobComplaintCreate,
    session: SessionDep,
    context: ManagerContext,
) -> None:
    async with session.begin():
        await create_complaint(session, context, job_id, payload)
        await bump_sync_revisions(session, context.business_id, "jobs", "customers")


@router.post("/jobs/{job_id}/quality/complaints/{complaint_id}/review", status_code=204)
async def job_quality_complaint_review(
    job_id: uuid.UUID,
    complaint_id: uuid.UUID,
    payload: JobComplaintReview,
    session: SessionDep,
    context: ManagerContext,
) -> None:
    async with session.begin():
        await review_complaint(session, context, job_id, complaint_id, payload)
        domains = (
            ("jobs", "schedule", "finance", "customers")
            if payload.decision == "approve_rewash"
            else ("jobs",)
        )
        await bump_sync_revisions(session, context.business_id, *domains)


@router.post("/jobs/{job_id}/start-trip", response_model=StaffJob)
async def job_start_trip(
    job_id: uuid.UUID,
    payload: StartTripAction,
    request: Request,
    session: SessionDep,
    context: Annotated[StaffContext, Depends(staff_context)],
) -> StaffJob:
    settings = get_settings()
    provider = (
        GoogleRoutesEtaProvider(
            cast(httpx.AsyncClient, request.app.state.http_client), settings.google_routes_api_key
        )
        if settings.google_routes_api_key
        else None
    )
    snapshot = await get_job(session, context, job_id)
    await session.rollback()
    eta = None
    if (
        provider
        and payload.origin is not None
        and snapshot.latitude is not None
        and snapshot.longitude is not None
    ):
        try:
            eta = await provider.estimate(
                origin=(payload.origin.latitude, payload.origin.longitude),
                destination=(snapshot.latitude, snapshot.longitude),
            )
        except Exception:
            logger.warning("eta_provider_failed", job_id=str(job_id))
    async with session.begin():
        result = await start_trip(session, context, job_id, payload, eta)
        await bump_sync_revisions(session, context.business_id, "jobs", "customers")
        return result


@router.post("/jobs/{job_id}/start", response_model=StaffJob)
async def job_start(
    job_id: uuid.UUID,
    payload: JobAction,
    session: SessionDep,
    context: Annotated[StaffContext, Depends(staff_context)],
) -> StaffJob:
    async with session.begin():
        result = await transition_job(session, context, job_id, payload, JobStatus.IN_PROGRESS)
        await bump_sync_revisions(session, context.business_id, "jobs", "customers")
        return result


@router.post("/jobs/{job_id}/arrive", response_model=StaffJob)
async def job_arrive(
    job_id: uuid.UUID,
    payload: JobAction,
    session: SessionDep,
    context: Annotated[StaffContext, Depends(staff_context)],
) -> StaffJob:
    async with session.begin():
        result = await transition_job(session, context, job_id, payload, JobStatus.ARRIVED)
        await bump_sync_revisions(session, context.business_id, "jobs", "customers")
        return result


@router.post("/jobs/{job_id}/complete", response_model=StaffJob)
async def job_complete(
    job_id: uuid.UUID,
    payload: JobAction,
    session: SessionDep,
    context: Annotated[StaffContext, Depends(staff_context)],
) -> StaffJob:
    async with session.begin():
        result = await transition_job(session, context, job_id, payload, JobStatus.COMPLETED)
        await bump_sync_revisions(session, context.business_id, "jobs", "customers")
        return result


@router.post("/jobs/{job_id}/cash-payment", response_model=CashPaymentResult)
async def job_cash(
    job_id: uuid.UUID,
    payload: CashTenderAction,
    session: SessionDep,
    context: Annotated[StaffContext, Depends(staff_context)],
) -> CashPaymentResult:
    async with session.begin():
        result = await record_cash(session, context, job_id, payload)
        await bump_sync_revisions(session, context.business_id, "jobs", "finance", "customers")
        return result


@router.patch("/jobs/{job_id}/assignment", response_model=StaffJob)
async def job_assignment(
    job_id: uuid.UUID, payload: AssignmentAction, session: SessionDep, context: ManagerContext
) -> StaffJob:
    async with session.begin():
        result = await assign_job(session, context, job_id, payload)
        await bump_sync_revisions(session, context.business_id, "jobs", "schedule")
        return result


@router.get("/team", response_model=list[StaffMember])
async def team(session: SessionDep, context: ManagerContext) -> list[StaffMember]:
    return await list_team(session, context)


@router.get("/reports/summary", response_model=ReportSummary)
async def reports(
    start_date: date, end_date: date, session: SessionDep, context: ManagerContext
) -> ReportSummary:
    return await report_summary(session, context, start_date, end_date)


@router.get("/cancellations", response_model=list[CancellationItem])
async def cancellations(session: SessionDep, context: ManagerContext) -> list[CancellationItem]:
    return await list_cancellations(session, context)


@router.post("/cancellations/{cancellation_id}/review", response_model=CancellationItem)
async def cancellation_review(
    cancellation_id: uuid.UUID,
    payload: CancellationReview,
    session: SessionDep,
    context: ManagerContext,
) -> CancellationItem:
    async with session.begin():
        result = await review_cancellation(session, context, cancellation_id, payload)
        await bump_sync_revisions(session, context.business_id, "jobs", "schedule", "customers")
        return result


@router.get("/customers", response_model=ManagerCustomerList)
async def manager_customers(
    session: SessionDep,
    context: ManagerContext,
    search: str | None = Query(default=None, max_length=160),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=50),
) -> ManagerCustomerList:
    return await list_manager_customers(session, context, search=search, offset=offset, limit=limit)


@router.get("/customers/{customer_id}", response_model=ManagerCustomerDetail)
async def manager_customer(
    customer_id: uuid.UUID,
    session: SessionDep,
    context: ManagerContext,
    history_offset: int = Query(default=0, ge=0),
    history_limit: int = Query(default=30, ge=1, le=50),
) -> ManagerCustomerDetail:
    return await manager_customer_detail(
        session,
        context,
        customer_id,
        history_offset=history_offset,
        history_limit=history_limit,
    )


@router.patch("/customers/{customer_id}", response_model=ManagerCustomerDetail)
async def manager_customer_update(
    customer_id: uuid.UUID,
    payload: ManagerCustomerUpdate,
    session: SessionDep,
    context: ManagerContext,
) -> ManagerCustomerDetail:
    async with session.begin():
        result = await update_manager_customer(session, context, customer_id, payload)
        await bump_sync_revisions(session, context.business_id, "customers")
        return result


@router.post(
    "/customers/{customer_id}/addresses",
    response_model=CustomerAddressResponse,
    status_code=201,
)
async def manager_customer_address_create(
    customer_id: uuid.UUID,
    payload: CustomerAddressWrite,
    session: SessionDep,
    context: ManagerContext,
) -> CustomerAddressResponse:
    async with session.begin():
        result = await create_manager_address(session, context, customer_id, payload)
        await bump_sync_revisions(session, context.business_id, "customers")
        return result


@router.patch(
    "/customers/{customer_id}/addresses/{address_id}",
    response_model=CustomerAddressResponse,
)
async def manager_customer_address_update(
    customer_id: uuid.UUID,
    address_id: uuid.UUID,
    payload: CustomerAddressWrite,
    session: SessionDep,
    context: ManagerContext,
) -> CustomerAddressResponse:
    async with session.begin():
        result = await update_manager_address(session, context, customer_id, address_id, payload)
        await bump_sync_revisions(session, context.business_id, "customers")
        return result


@router.delete("/customers/{customer_id}/addresses/{address_id}", status_code=204)
async def manager_customer_address_delete(
    customer_id: uuid.UUID,
    address_id: uuid.UUID,
    session: SessionDep,
    context: ManagerContext,
) -> Response:
    async with session.begin():
        await delete_manager_address(session, context, customer_id, address_id)
        await bump_sync_revisions(session, context.business_id, "customers")
    return Response(status_code=204)


@router.post(
    "/customers/{customer_id}/vehicles",
    response_model=CustomerVehicleResponse,
    status_code=201,
)
async def manager_customer_vehicle_create(
    customer_id: uuid.UUID,
    payload: CustomerVehicleWrite,
    session: SessionDep,
    context: ManagerContext,
) -> CustomerVehicleResponse:
    async with session.begin():
        result = await create_manager_vehicle(session, context, customer_id, payload)
        await bump_sync_revisions(session, context.business_id, "customers")
        return result


@router.patch(
    "/customers/{customer_id}/vehicles/{vehicle_id}",
    response_model=CustomerVehicleResponse,
)
async def manager_customer_vehicle_update(
    customer_id: uuid.UUID,
    vehicle_id: uuid.UUID,
    payload: CustomerVehicleWrite,
    session: SessionDep,
    context: ManagerContext,
) -> CustomerVehicleResponse:
    async with session.begin():
        result = await update_manager_vehicle(session, context, customer_id, vehicle_id, payload)
        await bump_sync_revisions(session, context.business_id, "customers")
        return result


@router.delete("/customers/{customer_id}/vehicles/{vehicle_id}", status_code=204)
async def manager_customer_vehicle_delete(
    customer_id: uuid.UUID,
    vehicle_id: uuid.UUID,
    session: SessionDep,
    context: ManagerContext,
) -> Response:
    async with session.begin():
        await deactivate_manager_vehicle(session, context, customer_id, vehicle_id)
        await bump_sync_revisions(session, context.business_id, "customers")
    return Response(status_code=204)


@router.post("/customers/{customer_id}/loyalty/adjustments", response_model=LoyaltySummary)
async def manager_customer_loyalty_adjustment(
    customer_id: uuid.UUID,
    payload: LoyaltyAdjustment,
    session: SessionDep,
    context: ManagerContext,
) -> LoyaltySummary:
    async with session.begin():
        result = await adjust_loyalty(
            session,
            business_id=context.business_id,
            customer_profile_id=customer_id,
            actor_staff_id=context.staff_id,
            request=payload,
        )
        await bump_sync_revisions(session, context.business_id, "customers")
        return result


@router.get("/loyalty/settings", response_model=LoyaltySettingsView)
async def loyalty_settings(session: SessionDep, context: ManagerContext) -> LoyaltySettingsView:
    return await get_loyalty_settings(session, context.business_id)


@router.patch("/loyalty/settings", response_model=LoyaltySettingsView)
async def loyalty_settings_update(
    payload: LoyaltySettingsUpdate, session: SessionDep, context: ManagerContext
) -> LoyaltySettingsView:
    async with session.begin():
        result = await update_loyalty_settings(session, context.business_id, payload)
        await bump_sync_revisions(session, context.business_id, "customers")
        return result


@router.post("/bookings/{booking_id}/reschedule", response_model=StaffJob)
async def manager_reschedule(
    booking_id: uuid.UUID,
    payload: ManagerRescheduleCreate,
    session: SessionDep,
    context: ManagerContext,
) -> StaffJob:
    async with session.begin():
        booking = (
            await session.scalars(
                select(Booking)
                .where(Booking.id == booking_id, Booking.business_id == context.business_id)
                .with_for_update()
            )
        ).one_or_none()
        if booking is None:
            raise DomainError("BOOKING_NOT_FOUND", "Booking not found.", status_code=404)
        await reschedule_managed_booking(
            session,
            booking,
            payload,
            actor_staff_id=context.staff_id,
            confirm_active_reschedule=payload.confirm_active_reschedule,
        )
        job = (await session.scalars(select(Job).where(Job.booking_id == booking.id))).one()
        await session.flush()
        result = await get_job(session, context, job.id)
        await bump_sync_revisions(session, context.business_id, "jobs", "schedule", "customers")
        return result

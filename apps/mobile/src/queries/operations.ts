import { useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  assignJob,
  addJobQualityIssue,
  assignShift,
  clockAttendance,
  createHold,
  createCashReconciliation,
  createExpense,
  createInventoryItem,
  createInventoryLocation,
  createManagerCustomerAddress,
  createManagerCustomerVehicle,
  createJobComplaint,
  createStaff,
  createShift,
  createTeam,
  getAttendance,
  getAttendanceOverview,
  getAvailability,
  getCancellations,
  getDashboard,
  getCashReconciliations,
  getExpenses,
  getFinanceOverview,
  getInventoryItems,
  getInventoryLocations,
  getInventoryMovements,
  getInventoryOverview,
  getInventoryStock,
  getJob,
  getJobQuality,
  getJobs,
  getLeave,
  getLoyaltySettings,
  getManagerCustomer,
  getManagerCustomers,
  getProfile,
  getPendingCash,
  getPendingCashDetail,
  getPersonalCash,
  getReport,
  getShiftAssignments,
  getShifts,
  getServiceOptions,
  getStaff,
  getTeam,
  getTeamStockSummary,
  getTeams,
  mutateJob,
  receiveInventoryStock,
  recordCashPayment,
  recordInventoryStockCount,
  recordInventoryUsage,
  recordInventoryWastage,
  adjustManagerCustomerLoyalty,
  deleteManagerCustomerAddress,
  deleteManagerCustomerVehicle,
  reviewJobComplaint,
  rescheduleJob,
  reviewCancellation,
  reviewLeave,
  requestLeave,
  saveJobChecklist,
  saveJobInspection,
  updateStaff,
  updateProfile,
  updateLoyaltySettings,
  updateInventoryItem,
  updateManagerCustomer,
  updateManagerCustomerAddress,
  updateManagerCustomerVehicle,
  updateTeam,
  updateTeamMembers,
  transferInventoryStock,
  uploadJobPhoto,
  voidCashReconciliation,
  voidExpense,
  type Attendance,
  type Cancellation,
  type CashPendingDetail,
  type Dashboard,
  type Expense,
  type ExpenseFilters,
  type InventoryLocation,
  type Job,
  type JobPhoto,
  type JobFilters,
  type Leave,
  type ManagerCustomerDetail,
  type Profile,
  type ShiftAssignment,
  type StaffContext,
  type Team,
  type TeamDetail,
} from "../lib";
import {
  cacheTimes,
  operationalScope,
  persistedQueryMeta,
  queryKeys,
  replaceJobInResponse,
  retentionTimes,
} from "../cache/policy";
import { reschedulePayload } from "../operations";
import { ClientEventIdStore } from "../idempotency/clientEventId";

const day = () => new Date().toISOString().slice(0, 10);

export function useJobsQuery(
  context: StaffContext,
  filters: JobFilters,
  enabled = true,
) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.jobs(scope, filters),
    queryFn: ({ signal }) => getJobs(filters, signal),
    staleTime: cacheTimes.jobs,
    enabled,
    meta: persistedQueryMeta(retentionTimes.jobs),
  });
}

export function useManagerCustomersQuery(
  context: StaffContext,
  search: string,
  offset: number,
) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.customers(scope, search, offset),
    queryFn: ({ signal }) => getManagerCustomers(search, offset, signal),
    staleTime: cacheTimes.customers,
    meta: persistedQueryMeta(retentionTimes.customers),
  });
}

export function useManagerCustomerQuery(
  context: StaffContext,
  customerId: string,
  historyOffset = 0,
) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.customer(scope, customerId, historyOffset),
    queryFn: ({ signal }) =>
      getManagerCustomer(customerId, historyOffset, signal),
    staleTime: cacheTimes.customers,
    meta: persistedQueryMeta(retentionTimes.customers),
  });
}

function useCustomerInvalidation(context: StaffContext, customerId: string) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return (detail?: ManagerCustomerDetail) => {
    if (detail)
      client.setQueryData(queryKeys.customer(scope, customerId), detail);
    void client.invalidateQueries({ queryKey: ["customers", scope] });
    void client.invalidateQueries({
      queryKey: queryKeys.customer(scope, customerId),
    });
  };
}

export function useUpdateManagerCustomerMutation(
  context: StaffContext,
  customerId: string,
) {
  const invalidate = useCustomerInvalidation(context, customerId);
  return useMutation({
    mutationFn: (body: object) => updateManagerCustomer(customerId, body),
    onSuccess: invalidate,
  });
}

export function useManagerAddressMutation(
  context: StaffContext,
  customerId: string,
) {
  const invalidate = useCustomerInvalidation(context, customerId);
  return useMutation({
    mutationFn: async ({
      action,
      id,
      body,
    }: {
      action: "create" | "update" | "delete";
      id?: string;
      body?: object;
    }) => {
      if (action === "create")
        await createManagerCustomerAddress(customerId, body ?? {});
      else if (action === "update" && id)
        await updateManagerCustomerAddress(customerId, id, body ?? {});
      else if (action === "delete" && id)
        await deleteManagerCustomerAddress(customerId, id);
      else throw new Error("Invalid address operation");
    },
    onSuccess: () => invalidate(),
  });
}

export function useManagerVehicleMutation(
  context: StaffContext,
  customerId: string,
) {
  const invalidate = useCustomerInvalidation(context, customerId);
  return useMutation({
    mutationFn: async ({
      action,
      id,
      body,
    }: {
      action: "create" | "update" | "delete";
      id?: string;
      body?: object;
    }) => {
      if (action === "create")
        await createManagerCustomerVehicle(customerId, body ?? {});
      else if (action === "update" && id)
        await updateManagerCustomerVehicle(customerId, id, body ?? {});
      else if (action === "delete" && id)
        await deleteManagerCustomerVehicle(customerId, id);
      else throw new Error("Invalid vehicle operation");
    },
    onSuccess: () => invalidate(),
  });
}

export function useLoyaltyAdjustmentMutation(
  context: StaffContext,
  customerId: string,
) {
  const invalidate = useCustomerInvalidation(context, customerId);
  return useMutation({
    mutationFn: (body: object) =>
      adjustManagerCustomerLoyalty(customerId, body),
    onSuccess: () => invalidate(),
  });
}

export function useLoyaltySettingsQuery(context: StaffContext) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.loyaltySettings(scope),
    queryFn: getLoyaltySettings,
    staleTime: cacheTimes.customers,
  });
}

export function useServiceOptionsQuery() {
  return useQuery({
    queryKey: queryKeys.serviceOptions,
    queryFn: getServiceOptions,
    staleTime: 5 * 60_000,
  });
}

export function useUpdateLoyaltySettingsMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: updateLoyaltySettings,
    onSuccess: (settings) => {
      client.setQueryData(queryKeys.loyaltySettings(scope), settings);
      void client.invalidateQueries({ queryKey: ["customer", scope] });
      void client.invalidateQueries({ queryKey: ["customers", scope] });
    },
  });
}

export function useJobQuery(
  context: StaffContext,
  id: string,
  placeholder?: Job,
) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.job(scope, id),
    queryFn: ({ signal }) => getJob(id, signal),
    placeholderData: placeholder,
    staleTime: cacheTimes.activeJob,
    meta: persistedQueryMeta(retentionTimes.job),
  });
}

export function useJobQualityQuery(
  context: StaffContext,
  jobId: string,
  enabled = true,
) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.quality(scope, jobId),
    queryFn: ({ signal }) => getJobQuality(jobId, signal),
    staleTime: cacheTimes.quality,
    meta: persistedQueryMeta(retentionTimes.quality),
    enabled,
  });
}

function useQualityInvalidation(context: StaffContext, jobId: string) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return () => {
    void client.invalidateQueries({
      queryKey: queryKeys.quality(scope, jobId),
    });
    void client.invalidateQueries({ queryKey: queryKeys.job(scope, jobId) });
  };
}

export function useInspectionMutation(context: StaffContext, jobId: string) {
  const invalidate = useQualityInvalidation(context, jobId);
  return useMutation({
    mutationFn: (body: object) => saveJobInspection(jobId, body),
    onSuccess: invalidate,
  });
}

export function useChecklistMutation(context: StaffContext, jobId: string) {
  const invalidate = useQualityInvalidation(context, jobId);
  const eventIds = useRef(new ClientEventIdStore()).current;
  return useMutation({
    mutationFn: async (items: { id: string; completed: boolean }[]) => {
      const key = `${jobId}:${JSON.stringify(items)}`;
      try {
        const result = await saveJobChecklist(jobId, {
          items,
          client_event_id: eventIds.get(key),
        });
        eventIds.succeeded(key);
        return result;
      } catch (error) {
        eventIds.failed(key, error);
        throw error;
      }
    },
    onSuccess: invalidate,
  });
}

export function useQualityIssueMutation(context: StaffContext, jobId: string) {
  const invalidate = useQualityInvalidation(context, jobId);
  return useMutation({
    mutationFn: (body: object) => addJobQualityIssue(jobId, body),
    onSuccess: invalidate,
  });
}

export function usePhotoUploadMutation(context: StaffContext, jobId: string) {
  const invalidate = useQualityInvalidation(context, jobId);
  return useMutation({
    mutationFn: ({
      uri,
      category,
      caption,
      clientRequestId,
    }: {
      uri: string;
      category: JobPhoto["category"];
      caption?: string;
      clientRequestId: string;
    }) => uploadJobPhoto(jobId, uri, category, clientRequestId, caption),
    onSuccess: invalidate,
  });
}

export function useComplaintMutation(context: StaffContext, jobId: string) {
  const invalidate = useQualityInvalidation(context, jobId);
  return useMutation({
    mutationFn: (description: string) => createJobComplaint(jobId, description),
    onSuccess: invalidate,
  });
}

export function useComplaintReviewMutation(context: StaffContext, job: Job) {
  const invalidate = useQualityInvalidation(context, job.id);
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: async ({
      complaintId,
      decision,
      reviewNote,
      appointment,
    }: {
      complaintId: string;
      decision: "under_review" | "resolved" | "rejected" | "approve_rewash";
      reviewNote?: string;
      appointment?: { day: string; startTime: string; resourceId: string };
    }) => {
      let holdToken: string | undefined;
      if (decision === "approve_rewash") {
        if (!appointment)
          throw new Error("A correction appointment is required.");
        const hold = await createHold(
          appointment.day,
          appointment.startTime,
          Math.max(1, job.vehicles.length),
          appointment.resourceId,
        );
        holdToken = hold.hold_token;
      }
      return reviewJobComplaint(job.id, complaintId, {
        decision,
        review_note: reviewNote?.trim() || null,
        ...(holdToken ? { hold_token: holdToken } : {}),
      });
    },
    onSuccess: (_result, variables) => {
      invalidate();
      if (variables.decision !== "approve_rewash") return;
      void client.invalidateQueries({ queryKey: ["jobs", scope] });
      void client.invalidateQueries({ queryKey: ["availability", scope] });
      void client.invalidateQueries({ queryKey: ["dashboard", scope] });
      void client.invalidateQueries({ queryKey: ["reports", scope] });
    },
  });
}

export function useDashboardQuery(
  context: StaffContext,
  businessDay = day(),
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.dashboard(operationalScope(context), businessDay),
    queryFn: () => getDashboard(businessDay),
    staleTime: cacheTimes.dashboard,
    enabled,
    meta: persistedQueryMeta(retentionTimes.dashboard),
  });
}

export function useProfileQuery(context: StaffContext) {
  return useQuery({
    queryKey: queryKeys.profile(operationalScope(context)),
    queryFn: getProfile,
    staleTime: cacheTimes.profile,
    meta: persistedQueryMeta(retentionTimes.profile),
  });
}

export function useTeamsQuery(context: StaffContext) {
  return useQuery({
    queryKey: queryKeys.teams(operationalScope(context)),
    queryFn: getTeams,
    staleTime: cacheTimes.teams,
    meta: persistedQueryMeta(retentionTimes.teams),
  });
}

export function useTeamQuery(
  context: StaffContext,
  teamId: string,
  enabled = true,
) {
  return useQuery<TeamDetail>({
    queryKey: queryKeys.team(operationalScope(context), teamId),
    queryFn: () => getTeam(teamId),
    staleTime: cacheTimes.teams,
    enabled: enabled && Boolean(teamId),
    meta: persistedQueryMeta(retentionTimes.team),
  });
}

export function useTeamStockSummaryQuery(
  context: StaffContext,
  teamId: string,
  enabled = true,
) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.teamStock(scope, teamId),
    queryFn: () => getTeamStockSummary(teamId),
    enabled: enabled && Boolean(teamId),
    staleTime: cacheTimes.inventory,
    meta: persistedQueryMeta(retentionTimes.inventory),
  });
}

export function useCreateTeamMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: createTeam,
    onSuccess: (created) => {
      client.setQueryData(queryKeys.team(scope, created.id), created);
      client.setQueryData(queryKeys.teams(scope), (current: unknown) =>
        Array.isArray(current) ? [...current, created] : [created],
      );
    },
  });
}

export function useUpdateTeamMembersMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: ({
      teamId,
      staffIds,
    }: {
      teamId: string;
      staffIds: string[];
    }) => updateTeamMembers(teamId, staffIds),
    onSuccess: (team) => {
      client.setQueryData(queryKeys.team(scope, team.id), team);
      client.setQueryData<Team[]>(
        queryKeys.teams(scope),
        (current) =>
          current?.map((item) =>
            item.id === team.id
              ? { ...item, member_count: team.members.length }
              : item,
          ) ?? [team],
      );
      const memberIds = new Set(team.members.map((member) => member.id));
      client.setQueryData<Profile[]>(queryKeys.staff(scope), (current) =>
        current?.map((profile) => {
          const withoutTeam = profile.teams.filter(
            (item) => item.id !== team.id,
          );
          return {
            ...profile,
            teams: memberIds.has(profile.id)
              ? [...withoutTeam, { id: team.id, name: team.name }]
              : withoutTeam,
          };
        }),
      );
    },
  });
}

export function useUpdateTeamMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: ({ teamId, body }: { teamId: string; body: object }) =>
      updateTeam(teamId, body),
    onSuccess: (team) => {
      client.setQueryData(queryKeys.team(scope, team.id), team);
      client.setQueryData<Team[]>(
        queryKeys.teams(scope),
        (current) =>
          current?.map((item) =>
            item.id === team.id ? { ...item, ...team } : item,
          ) ?? [team],
      );
    },
  });
}

export function useStaffQuery(context: StaffContext) {
  return useQuery({
    queryKey: queryKeys.staff(operationalScope(context)),
    queryFn: getStaff,
    staleTime: cacheTimes.staff,
    meta: persistedQueryMeta(retentionTimes.staff),
  });
}

export function useCreateStaffMutation(context: StaffContext) {
  const client = useQueryClient();
  const key = queryKeys.staff(operationalScope(context));
  return useMutation({
    mutationFn: createStaff,
    onSuccess: (created) => {
      client.setQueryData<Profile[]>(key, (current) =>
        current ? [...current, created] : [created],
      );
    },
  });
}

export function useUpdateStaffMutation(context: StaffContext) {
  const client = useQueryClient();
  const key = queryKeys.staff(operationalScope(context));
  return useMutation({
    mutationFn: ({ staffId, body }: { staffId: string; body: object }) =>
      updateStaff(staffId, body),
    onSuccess: (updated) => {
      client.setQueryData<Profile[]>(
        key,
        (current) =>
          current?.map((item) => (item.id === updated.id ? updated : item)) ?? [
            updated,
          ],
      );
    },
  });
}

export function useAttendanceOverviewQuery(
  context: StaffContext,
  businessDay = day(),
) {
  return useQuery({
    queryKey: queryKeys.attendance(operationalScope(context), businessDay),
    queryFn: () => getAttendanceOverview(businessDay),
    staleTime: cacheTimes.attendance,
    meta: persistedQueryMeta(retentionTimes.attendance),
  });
}

export function useAttendanceHistoryQuery(
  context: StaffContext,
  start: string,
  end: string,
) {
  return useQuery({
    queryKey: queryKeys.attendanceHistory(
      operationalScope(context),
      start,
      end,
    ),
    queryFn: () => getAttendance(start, end),
    staleTime: cacheTimes.attendance,
    meta: persistedQueryMeta(retentionTimes.attendance),
  });
}

export function useShiftsQuery(context: StaffContext) {
  return useQuery({
    queryKey: queryKeys.shifts(operationalScope(context)),
    queryFn: getShifts,
    staleTime: cacheTimes.shifts,
    meta: persistedQueryMeta(retentionTimes.shifts),
  });
}

export function useShiftAssignmentsQuery(
  context: StaffContext,
  start = day(),
  end = day(),
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.shiftAssignments(operationalScope(context), start, end),
    queryFn: () => getShiftAssignments(start, end),
    staleTime: cacheTimes.attendance,
    enabled,
    meta: persistedQueryMeta(retentionTimes.shifts),
  });
}

export function useLeaveQuery(context: StaffContext, status?: string) {
  return useQuery({
    queryKey: queryKeys.leave(operationalScope(context), status),
    queryFn: () => getLeave(status),
    staleTime: cacheTimes.attendance,
    meta: persistedQueryMeta(retentionTimes.leave),
  });
}

export function useCancellationsQuery(context: StaffContext) {
  return useQuery({
    queryKey: queryKeys.cancellations(operationalScope(context)),
    queryFn: getCancellations,
    staleTime: cacheTimes.attendance,
    meta: persistedQueryMeta(retentionTimes.cancellations),
  });
}

export function useReportQuery(
  context: StaffContext,
  start: string,
  end: string,
) {
  return useQuery({
    queryKey: queryKeys.reports(operationalScope(context), start, end),
    queryFn: () => getReport(start, end),
    staleTime: end < day() ? 5 * 60_000 : cacheTimes.reports,
    meta: persistedQueryMeta(retentionTimes.reports),
  });
}

export function useFinanceOverviewQuery(
  context: StaffContext,
  start: string,
  end: string,
) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.finance(scope, start, end),
    queryFn: () => getFinanceOverview(start, end),
    staleTime: cacheTimes.finance,
    meta: persistedQueryMeta(retentionTimes.finance),
  });
}

export function useInventoryOverviewQuery(
  context: StaffContext,
  enabled = true,
) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.inventoryOverview(scope),
    queryFn: getInventoryOverview,
    enabled,
    staleTime: cacheTimes.inventory,
    meta: persistedQueryMeta(retentionTimes.inventory),
  });
}

export function useInventoryItemsQuery(
  context: StaffContext,
  search = "",
  offset = 0,
) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.inventoryItems(scope, search, offset),
    queryFn: () => getInventoryItems(search, offset),
    staleTime: cacheTimes.inventory,
    meta: persistedQueryMeta(retentionTimes.inventory),
  });
}

export function useInventoryLocationsQuery(context: StaffContext) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.inventoryLocations(scope),
    queryFn: getInventoryLocations,
    staleTime: cacheTimes.inventory,
    meta: persistedQueryMeta(retentionTimes.inventory),
  });
}

export function useInventoryStockQuery(
  context: StaffContext,
  locationId = "",
  search = "",
  status = "",
  enabled = true,
) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.inventoryStock(scope, locationId, search, status),
    queryFn: () => getInventoryStock(locationId, search, status),
    enabled,
    staleTime: cacheTimes.inventory,
    meta: persistedQueryMeta(retentionTimes.inventory),
  });
}

export function useInventoryMovementsQuery(
  context: StaffContext,
  locationId = "",
  enabled = true,
) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.inventoryMovements(scope, locationId),
    queryFn: () => getInventoryMovements(locationId),
    enabled,
    staleTime: cacheTimes.inventory,
    meta: persistedQueryMeta(retentionTimes.inventory),
  });
}

type InventoryMutationInput =
  | { action: "create_item"; body: object }
  | { action: "edit_item"; itemId: string; body: object }
  | { action: "create_location"; body: object }
  | {
      action: "receive" | "transfer" | "usage" | "wastage" | "stock_count";
      body: object;
    };

export function useInventoryMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  const eventIds = useRef(new ClientEventIdStore()).current;
  return useMutation({
    mutationFn: async (input: InventoryMutationInput) => {
      const { action, body } = input;
      if (action === "create_item") return createInventoryItem(body);
      if (action === "edit_item")
        return updateInventoryItem(input.itemId, body);
      if (action === "create_location")
        return createInventoryLocation(body) as Promise<InventoryLocation>;
      const key = `${action}:${JSON.stringify(body)}`;
      const payload = { ...body, client_event_id: eventIds.get(key) };
      try {
        const result =
          action === "receive"
            ? await receiveInventoryStock(payload)
            : action === "transfer"
              ? await transferInventoryStock(payload)
              : action === "usage"
                ? await recordInventoryUsage(payload)
                : action === "wastage"
                  ? await recordInventoryWastage(payload)
                  : await recordInventoryStockCount(payload);
        eventIds.succeeded(key);
        return result;
      } catch (error) {
        eventIds.failed(key, error);
        throw error;
      }
    },
    onSuccess: (_result, input) => {
      void client.invalidateQueries({ queryKey: ["inventory-overview", scope] });
      void client.invalidateQueries({ queryKey: ["inventory-items", scope] });
      void client.invalidateQueries({ queryKey: ["inventory-locations", scope] });
      void client.invalidateQueries({ queryKey: ["inventory-stock", scope] });
      void client.invalidateQueries({ queryKey: ["inventory-movements", scope] });
      void client.invalidateQueries({ queryKey: ["team-stock", scope] });
      if (
        input.action === "receive" &&
        Boolean((input.body as { record_as_expense?: boolean }).record_as_expense)
      ) {
        void client.invalidateQueries({ queryKey: ["finance", scope] });
        void client.invalidateQueries({ queryKey: ["expenses", scope] });
        void client.invalidateQueries({ queryKey: ["reports", scope] });
      }
    },
  });
}

export function useExpensesQuery(
  context: StaffContext,
  start: string,
  end: string,
  filters: ExpenseFilters = {},
  cursor = "",
) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.expenses(scope, start, end, filters, cursor),
    queryFn: () => getExpenses(start, end, filters, cursor || undefined),
    staleTime: cacheTimes.finance,
    meta: persistedQueryMeta(retentionTimes.finance),
  });
}

export function useExpenseMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: createExpense,
    onSuccess: (expense: Expense) => {
      void client.invalidateQueries({ queryKey: ["expenses", scope] });
      void client.invalidateQueries({ queryKey: ["finance", scope] });
      void client.invalidateQueries({ queryKey: ["reports", scope] });
      return expense;
    },
  });
}

export function useVoidExpenseMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      voidExpense(id, reason),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["expenses", scope] });
      void client.invalidateQueries({ queryKey: ["finance", scope] });
      void client.invalidateQueries({ queryKey: ["reports", scope] });
    },
  });
}

export function usePendingCashQuery(context: StaffContext) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.cashPending(scope),
    queryFn: getPendingCash,
    staleTime: cacheTimes.finance,
    meta: persistedQueryMeta(retentionTimes.finance),
  });
}

export function usePendingCashDetailQuery(
  context: StaffContext,
  staffId: string,
) {
  const scope = operationalScope(context);
  return useQuery<CashPendingDetail>({
    queryKey: queryKeys.cashPendingDetail(scope, staffId),
    queryFn: () => getPendingCashDetail(staffId),
    enabled: Boolean(staffId),
    staleTime: cacheTimes.finance,
  });
}

export function useCashReconciliationsQuery(context: StaffContext) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.cashReconciliations(scope),
    queryFn: getCashReconciliations,
    staleTime: cacheTimes.finance,
    meta: persistedQueryMeta(retentionTimes.finance),
  });
}

export function useCashReconciliationMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: createCashReconciliation,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["cash-pending", scope] });
      void client.invalidateQueries({
        queryKey: ["cash-pending-detail", scope],
      });
      void client.invalidateQueries({
        queryKey: ["cash-reconciliations", scope],
      });
      void client.invalidateQueries({ queryKey: ["finance", scope] });
      void client.invalidateQueries({ queryKey: ["personal-cash", scope] });
    },
  });
}

export function useVoidCashReconciliationMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      voidCashReconciliation(id, reason),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["cash-pending", scope] });
      void client.invalidateQueries({
        queryKey: ["cash-reconciliations", scope],
      });
      void client.invalidateQueries({ queryKey: ["finance", scope] });
      void client.invalidateQueries({ queryKey: ["personal-cash", scope] });
    },
  });
}

export function usePersonalCashQuery(context: StaffContext, businessDay: string) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.personalCash(scope, businessDay),
    queryFn: () => getPersonalCash(businessDay),
    staleTime: cacheTimes.finance,
    meta: persistedQueryMeta(retentionTimes.finance),
  });
}

export function useAvailabilityQuery(
  context: StaffContext,
  bookingId: string,
  selectedDay: string,
  vehicleCount: number,
  enabled: boolean,
) {
  return useQuery({
    queryKey: queryKeys.availability(
      operationalScope(context),
      bookingId,
      selectedDay,
      vehicleCount,
    ),
    queryFn: ({ signal }) => getAvailability(selectedDay, vehicleCount, signal),
    staleTime: cacheTimes.availability,
    gcTime: 2 * 60_000,
    enabled,
    retry: false,
  });
}

function updateJobCaches(
  client: ReturnType<typeof useQueryClient>,
  scope: string,
  job: Job,
) {
  client.setQueryData(queryKeys.job(scope, job.id), job);
  client.setQueriesData<{ jobs: Job[]; next_offset: number | null }>(
    { queryKey: ["jobs", scope] },
    (current) => replaceJobInResponse(current, job),
  );
  client.setQueriesData<Dashboard>(
    { queryKey: ["dashboard", scope] },
    (current) =>
      current
        ? {
            ...current,
            active_jobs:
              job.status === "completed" || job.status === "cancelled"
                ? current.active_jobs.filter((item) => item.id !== job.id)
                : current.active_jobs.some((item) => item.id === job.id)
                  ? current.active_jobs.map((item) =>
                      item.id === job.id ? job : item,
                    )
                  : current.active_jobs,
          }
        : current,
  );
}

export function useJobActionMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: ({
      jobId,
      action,
      body,
    }: {
      jobId: string;
      action: "start-trip" | "arrive" | "start" | "complete";
      body: object;
    }) => mutateJob(jobId, action, body),
    onSuccess: (job, variables) => {
      updateJobCaches(client, scope, job);
      void client.invalidateQueries({ queryKey: ["dashboard", scope] });
      if (variables.action === "complete")
        void client.invalidateQueries({ queryKey: ["reports", scope] });
    },
  });
}

export function useCashPaymentMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: ({ jobId, body }: { jobId: string; body: object }) =>
      recordCashPayment(jobId, body),
    onSuccess: (receipt) => {
      updateJobCaches(client, scope, receipt.job);
      void client.invalidateQueries({ queryKey: ["reports", scope] });
      void client.invalidateQueries({ queryKey: ["finance", scope] });
      void client.invalidateQueries({ queryKey: ["cash-pending", scope] });
      void client.invalidateQueries({ queryKey: ["personal-cash", scope] });
      void client.invalidateQueries({ queryKey: ["customers", scope] });
    },
  });
}

export function useAssignJobMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: ({ jobId, body }: { jobId: string; body: object }) =>
      assignJob(jobId, body),
    onSuccess: (job) => {
      updateJobCaches(client, scope, job);
    },
  });
}

export function useRescheduleMutation(context: StaffContext, job: Job) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: async ({
      selectedDay,
      startTime,
      resourceId,
      confirmActiveReschedule,
    }: {
      selectedDay: string;
      startTime: string;
      resourceId: string;
      confirmActiveReschedule: boolean;
    }) => {
      const hold = await createHold(
        selectedDay,
        startTime,
        Math.max(1, job.vehicles.length),
        resourceId,
      );
      return rescheduleJob(job.booking_id, {
        ...reschedulePayload(hold.hold_token),
        confirm_active_reschedule: confirmActiveReschedule,
      });
    },
    onSuccess: (next) => {
      updateJobCaches(client, scope, next);
      void client.invalidateQueries({
        queryKey: ["availability", scope, job.booking_id],
      });
    },
  });
}

export function useClockMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: (action: "clock-in" | "clock-out") => clockAttendance(action),
    onSuccess: (item: Attendance) => {
      void client.invalidateQueries({ queryKey: ["attendance", scope] });
      void client.invalidateQueries({
        queryKey: ["attendance-history", scope],
      });
      void client.invalidateQueries({ queryKey: ["dashboard", scope] });
      return item;
    },
  });
}

export function useCreateShiftMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: createShift,
    onSuccess: (created) => {
      client.setQueryData(queryKeys.shifts(scope), (current: unknown) =>
        Array.isArray(current) ? [...current, created] : [created],
      );
    },
  });
}

export function useAssignShiftMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: assignShift,
    onSuccess: (assignment: ShiftAssignment) => {
      const assignmentQueries = client
        .getQueryCache()
        .findAll({ queryKey: ["shift-assignments", scope] });
      for (const query of assignmentQueries) {
        const start = query.queryKey[2];
        const end = query.queryKey[3];
        if (
          typeof start === "string" &&
          typeof end === "string" &&
          assignment.work_date >= start &&
          assignment.work_date <= end
        ) {
          client.setQueryData<ShiftAssignment[]>(query.queryKey, (current) =>
            current
              ? [
                  ...current.filter((item) => item.id !== assignment.id),
                  assignment,
                ]
              : [assignment],
          );
        }
      }
      void client.invalidateQueries({ queryKey: ["attendance", scope] });
      void client.invalidateQueries({ queryKey: ["dashboard", scope] });
      void client.invalidateQueries({ queryKey: ["profile", scope] });
    },
  });
}

export function useUpdateProfileMutation(context: StaffContext) {
  const client = useQueryClient();
  const key = queryKeys.profile(operationalScope(context));
  return useMutation({
    mutationFn: updateProfile,
    onSuccess: (profile) => client.setQueryData(key, profile),
  });
}

export function useRequestLeaveMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: requestLeave,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["leave", scope] });
      void client.invalidateQueries({ queryKey: ["attendance", scope] });
      void client.invalidateQueries({ queryKey: ["dashboard", scope] });
    },
  });
}

export function useReviewLeaveMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: ({
      id,
      decision,
    }: {
      id: string;
      decision: "approved" | "rejected";
    }) => reviewLeave(id, decision),
    onSuccess: (updated: Leave) => {
      client.setQueryData<Leave[]>(
        queryKeys.leave(scope, "pending"),
        (current) => current?.filter((item) => item.id !== updated.id) ?? [],
      );
      client.setQueryData<Leave[]>(
        queryKeys.leave(scope),
        (current) =>
          current?.map((item) => (item.id === updated.id ? updated : item)) ?? [
            updated,
          ],
      );
      void client.invalidateQueries({ queryKey: ["attendance", scope] });
      void client.invalidateQueries({ queryKey: ["dashboard", scope] });
    },
  });
}

export function useReviewCancellationMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  const eventIds = useRef(new ClientEventIdStore()).current;
  return useMutation({
    mutationFn: async ({
      id,
      decision,
    }: {
      id: string;
      decision: "approved" | "rejected";
    }) => {
      const key = `${id}:${decision}`;
      try {
        const result = await reviewCancellation(
          id,
          decision,
          eventIds.get(key),
        );
        eventIds.succeeded(key);
        return result;
      } catch (error) {
        eventIds.failed(key, error);
        throw error;
      }
    },
    onSuccess: (updated: Cancellation) => {
      client.setQueryData<Cancellation[]>(
        queryKeys.cancellations(scope),
        (current) => current?.filter((item) => item.id !== updated.id) ?? [],
      );
      void client.invalidateQueries({ queryKey: ["jobs", scope] });
      void client.invalidateQueries({ queryKey: ["dashboard", scope] });
    },
  });
}

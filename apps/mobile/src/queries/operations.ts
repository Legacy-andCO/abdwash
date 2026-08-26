import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  assignJob,
  assignShift,
  clockAttendance,
  createHold,
  createStaff,
  createShift,
  createTeam,
  getAttendance,
  getAttendanceOverview,
  getAvailability,
  getCancellations,
  getDashboard,
  getJob,
  getJobs,
  getLeave,
  getProfile,
  getReport,
  getShiftAssignments,
  getShifts,
  getStaff,
  getTeam,
  getTeams,
  mutateJob,
  rescheduleJob,
  reviewCancellation,
  reviewLeave,
  requestLeave,
  updateStaff,
  updateProfile,
  updateTeam,
  updateTeamMembers,
  type Attendance,
  type Cancellation,
  type Dashboard,
  type Job,
  type JobFilters,
  type Leave,
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

const day = () => new Date().toISOString().slice(0, 10);

export function useJobsQuery(context: StaffContext, filters: JobFilters) {
  const scope = operationalScope(context);
  return useQuery({
    queryKey: queryKeys.jobs(scope, filters),
    queryFn: ({ signal }) => getJobs(filters, signal),
    staleTime: cacheTimes.jobs,
    meta: persistedQueryMeta(retentionTimes.jobs),
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
          const withoutTeam = profile.teams.filter((item) => item.id !== team.id);
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
      client.setQueryData<Profile[]>(key, (current) =>
        current?.map((item) => (item.id === updated.id ? updated : item)) ??
        [updated],
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
    queryKey: queryKeys.attendanceHistory(operationalScope(context), start, end),
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
) {
  return useQuery({
    queryKey: queryKeys.shiftAssignments(operationalScope(context), start, end),
    queryFn: () => getShiftAssignments(start, end),
    staleTime: cacheTimes.attendance,
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
      action: "start-trip" | "arrive" | "start" | "complete" | "cash-payment";
      body: object;
    }) => mutateJob(jobId, action, body),
    onSuccess: (job, variables) => {
      updateJobCaches(client, scope, job);
      void client.invalidateQueries({ queryKey: ["dashboard", scope] });
      if (variables.action === "complete" || variables.action === "cash-payment")
        void client.invalidateQueries({ queryKey: ["reports", scope] });
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
      client.setQueryData<Leave[]>(queryKeys.leave(scope), (current) =>
        current?.map((item) => (item.id === updated.id ? updated : item)) ??
        [updated],
      );
      void client.invalidateQueries({ queryKey: ["attendance", scope] });
      void client.invalidateQueries({ queryKey: ["dashboard", scope] });
    },
  });
}

export function useReviewCancellationMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  return useMutation({
    mutationFn: ({
      id,
      decision,
    }: {
      id: string;
      decision: "approved" | "rejected";
    }) => reviewCancellation(id, decision),
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

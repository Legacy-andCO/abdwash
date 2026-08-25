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
  getDashboard,
  getJob,
  getJobs,
  getLeave,
  getProfile,
  getReport,
  getShiftAssignments,
  getShifts,
  getStaff,
  getTeams,
  mutateJob,
  rescheduleJob,
  requestLeave,
  updateProfile,
  updateTeam,
  updateTeamMembers,
  type Attendance,
  type Job,
  type JobFilters,
  type Profile,
  type StaffContext,
  type Team,
} from "../lib";
import { cacheTimes, queryKeys, replaceJobInResponse } from "../cache/policy";
import { reschedulePayload } from "../operations";

const day = () => new Date().toISOString().slice(0, 10);
const scopeOf = (context: StaffContext) =>
  `${context.business_id}:${context.staff_id}`;

export function useJobsQuery(context: StaffContext, filters: JobFilters) {
  const scope = scopeOf(context);
  return useQuery({
    queryKey: queryKeys.jobs(scope, filters),
    queryFn: ({ signal }) => getJobs(filters, signal),
    staleTime: cacheTimes.jobs,
    meta: { persist: true },
  });
}

export function useJobQuery(
  context: StaffContext,
  id: string,
  placeholder?: Job,
) {
  const scope = scopeOf(context);
  return useQuery({
    queryKey: queryKeys.job(scope, id),
    queryFn: ({ signal }) => getJob(id, signal),
    placeholderData: placeholder,
    staleTime: cacheTimes.activeJob,
    meta: { persist: true },
  });
}

export function useDashboardQuery(
  context: StaffContext,
  businessDay = day(),
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.dashboard(scopeOf(context), businessDay),
    queryFn: () => getDashboard(businessDay),
    staleTime: cacheTimes.dashboard,
    enabled,
    meta: { persist: true },
  });
}

export function useProfileQuery(context: StaffContext) {
  return useQuery({
    queryKey: queryKeys.profile(scopeOf(context)),
    queryFn: getProfile,
    staleTime: cacheTimes.profile,
    meta: { persist: true },
  });
}

export function useTeamsQuery(context: StaffContext) {
  return useQuery({
    queryKey: queryKeys.teams(scopeOf(context)),
    queryFn: getTeams,
    staleTime: cacheTimes.teams,
    meta: { persist: true },
  });
}

export function useCreateTeamMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = scopeOf(context);
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
  const scope = scopeOf(context);
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
      void client.invalidateQueries({
        queryKey: ["staff", scope],
        refetchType: "none",
      });
    },
  });
}

export function useUpdateTeamMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = scopeOf(context);
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
    queryKey: queryKeys.staff(scopeOf(context)),
    queryFn: getStaff,
    staleTime: cacheTimes.staff,
    meta: { persist: true },
  });
}

export function useCreateStaffMutation(context: StaffContext) {
  const client = useQueryClient();
  const key = queryKeys.staff(scopeOf(context));
  return useMutation({
    mutationFn: createStaff,
    onSuccess: (created) => {
      client.setQueryData<Profile[]>(key, (current) =>
        current ? [...current, created] : [created],
      );
    },
  });
}

export function useAttendanceOverviewQuery(
  context: StaffContext,
  businessDay = day(),
) {
  return useQuery({
    queryKey: queryKeys.attendance(scopeOf(context), businessDay),
    queryFn: () => getAttendanceOverview(businessDay),
    staleTime: cacheTimes.attendance,
    meta: { persist: true },
  });
}

export function useAttendanceHistoryQuery(
  context: StaffContext,
  start: string,
  end: string,
) {
  return useQuery({
    queryKey: queryKeys.attendanceHistory(scopeOf(context), start, end),
    queryFn: () => getAttendance(start, end),
    staleTime: cacheTimes.attendance,
    meta: { persist: true },
  });
}

export function useShiftsQuery(context: StaffContext) {
  return useQuery({
    queryKey: queryKeys.shifts(scopeOf(context)),
    queryFn: getShifts,
    staleTime: cacheTimes.shifts,
    meta: { persist: true },
  });
}

export function useShiftAssignmentsQuery(
  context: StaffContext,
  start = day(),
  end = day(),
) {
  return useQuery({
    queryKey: queryKeys.shiftAssignments(scopeOf(context), start, end),
    queryFn: () => getShiftAssignments(start, end),
    staleTime: cacheTimes.attendance,
    meta: { persist: true },
  });
}

export function useLeaveQuery(context: StaffContext, status?: string) {
  return useQuery({
    queryKey: queryKeys.leave(scopeOf(context), status),
    queryFn: () => getLeave(status),
    staleTime: cacheTimes.attendance,
    meta: { persist: true },
  });
}

export function useReportQuery(
  context: StaffContext,
  start: string,
  end: string,
) {
  return useQuery({
    queryKey: queryKeys.reports(scopeOf(context), start, end),
    queryFn: () => getReport(start, end),
    staleTime: cacheTimes.reports,
    meta: { persist: true },
  });
}

export function useAvailabilityQuery(
  bookingId: string,
  selectedDay: string,
  vehicleCount: number,
  enabled: boolean,
) {
  return useQuery({
    queryKey: queryKeys.availability(bookingId, selectedDay, vehicleCount),
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
}

export function useJobActionMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = scopeOf(context);
  return useMutation({
    mutationFn: ({
      jobId,
      action,
      body,
    }: {
      jobId: string;
      action: "start-trip" | "start" | "complete" | "cash-payment";
      body: object;
    }) => mutateJob(jobId, action, body),
    onSuccess: (job) => {
      updateJobCaches(client, scope, job);
    },
  });
}

export function useAssignJobMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = scopeOf(context);
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
  const scope = scopeOf(context);
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
        queryKey: ["availability", job.booking_id],
      });
    },
  });
}

export function useClockMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = scopeOf(context);
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
  const scope = scopeOf(context);
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
  const scope = scopeOf(context);
  return useMutation({
    mutationFn: assignShift,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["shift-assignments", scope] });
      void client.invalidateQueries({ queryKey: ["attendance", scope] });
      void client.invalidateQueries({ queryKey: ["dashboard", scope] });
      void client.invalidateQueries({ queryKey: ["profile", scope] });
    },
  });
}

export function useUpdateProfileMutation(context: StaffContext) {
  const client = useQueryClient();
  const key = queryKeys.profile(scopeOf(context));
  return useMutation({
    mutationFn: updateProfile,
    onSuccess: (profile) => client.setQueryData(key, profile),
  });
}

export function useRequestLeaveMutation(context: StaffContext) {
  const client = useQueryClient();
  const scope = scopeOf(context);
  return useMutation({
    mutationFn: requestLeave,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["leave", scope] });
      void client.invalidateQueries({ queryKey: ["attendance", scope] });
      void client.invalidateQueries({ queryKey: ["dashboard", scope] });
    },
  });
}

import type { Job, JobFilters, StaffContext } from "../lib";

export const cacheTimes = {
  activeJob: 20_000,
  availability: 20_000,
  dashboard: 30_000,
  jobs: 30_000,
  teams: 3 * 60_000,
  staff: 3 * 60_000,
  attendance: 30_000,
  shifts: 5 * 60_000,
  profile: 5 * 60_000,
  reports: 2 * 60_000,
} as const;

export const retentionTimes = {
  dashboard: 24 * 60 * 60_000,
  jobs: 24 * 60 * 60_000,
  job: 24 * 60 * 60_000,
  teams: 2 * 24 * 60 * 60_000,
  team: 2 * 24 * 60 * 60_000,
  staff: 2 * 24 * 60 * 60_000,
  attendance: 24 * 60 * 60_000,
  shifts: 3 * 24 * 60 * 60_000,
  leave: 3 * 24 * 60 * 60_000,
  reports: 7 * 24 * 60 * 60_000,
  profile: 3 * 24 * 60 * 60_000,
  cancellations: 24 * 60 * 60_000,
} as const;

export function operationalScope(context: StaffContext) {
  return `${context.business_id}:${context.staff_id}:${context.role}`;
}

export function persistedQueryMeta(retentionMs: number) {
  return { persist: true, retentionMs } as const;
}

export const queryKeys = {
  context: ["staff-context"] as const,
  profile: (scope: string) => ["profile", scope] as const,
  dashboard: (scope: string, day: string) => ["dashboard", scope, day] as const,
  jobs: (scope: string, filters: JobFilters) =>
    ["jobs", scope, filters] as const,
  job: (scope: string, id: string) => ["job", scope, id] as const,
  teams: (scope: string) => ["teams", scope] as const,
  team: (scope: string, id: string) => ["team", scope, id] as const,
  staff: (scope: string) => ["staff", scope] as const,
  attendance: (scope: string, day: string) =>
    ["attendance", scope, day] as const,
  attendanceHistory: (scope: string, start: string, end: string) =>
    ["attendance-history", scope, start, end] as const,
  shifts: (scope: string) => ["shifts", scope] as const,
  shiftAssignments: (scope: string, start: string, end: string) =>
    ["shift-assignments", scope, start, end] as const,
  leave: (scope: string, status?: string) =>
    ["leave", scope, status ?? "all"] as const,
  cancellations: (scope: string) => ["cancellations", scope] as const,
  reports: (scope: string, start: string, end: string) =>
    ["reports", scope, start, end] as const,
  availability: (
    scope: string,
    bookingId: string,
    day: string,
    vehicleCount: number,
  ) => ["availability", scope, bookingId, day, vehicleCount] as const,
};

export function replaceJobInResponse(
  current: { jobs: Job[]; next_offset: number | null } | undefined,
  job: Job,
) {
  return current
    ? {
        ...current,
        jobs: current.jobs.map((item) => (item.id === job.id ? job : item)),
      }
    : current;
}

export function shouldShowPagination(
  offset: number,
  nextOffset: number | null | undefined,
) {
  return offset > 0 || nextOffset !== null;
}

export function assignmentLabel(job: Job) {
  if (job.assigned_team_name) return job.assigned_team_name;
  if (job.assigned_staff_name) return job.assigned_staff_name;
  if (job.assigned_team_id || job.assigned_staff_id) return "ASSIGNED";
  return "UNASSIGNED";
}

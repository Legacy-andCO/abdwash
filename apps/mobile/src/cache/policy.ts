import type { ExpenseFilters, Job, JobFilters, StaffContext } from "../lib";

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
  finance: 60_000,
  inventory: 60_000,
  catalogue: 60_000,
  quality: 30_000,
  customers: 60_000,
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
  finance: 7 * 24 * 60 * 60_000,
  inventory: 3 * 24 * 60 * 60_000,
  catalogue: 3 * 24 * 60 * 60_000,
  profile: 3 * 24 * 60 * 60_000,
  cancellations: 24 * 60 * 60_000,
  quality: 24 * 60 * 60_000,
  customers: 2 * 24 * 60 * 60_000,
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
  assignmentOptions: (scope: string, id: string) =>
    ["assignment-options", scope, id] as const,
  quality: (scope: string, id: string) => ["quality", scope, id] as const,
  customers: (scope: string, search: string, offset: number) =>
    ["customers", scope, search, offset] as const,
  customer: (scope: string, id: string, historyOffset = 0) =>
    ["customer", scope, id, historyOffset] as const,
  loyaltySettings: (scope: string) => ["loyalty-settings", scope] as const,
  serviceOptions: ["service-options"] as const,
  managedCatalogue: (scope: string) => ["managed-catalogue", scope] as const,
  businessSettings: (scope: string) => ["business-settings", scope] as const,
  serviceTemplate: (scope: string, serviceId: string) =>
    ["service-template", scope, serviceId] as const,
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
  finance: (scope: string, start: string, end: string) =>
    ["finance", scope, start, end] as const,
  expenses: (
    scope: string,
    start: string,
    end: string,
    filters: ExpenseFilters = {},
    cursor = "",
  ) => ["expenses", scope, start, end, filters, cursor] as const,
  cashPending: (scope: string) => ["cash-pending", scope] as const,
  cashPendingDetail: (scope: string, staffId: string) =>
    ["cash-pending-detail", scope, staffId] as const,
  cashReconciliations: (scope: string) =>
    ["cash-reconciliations", scope] as const,
  personalCash: (scope: string, day: string) =>
    ["personal-cash", scope, day] as const,
  inventoryOverview: (scope: string) => ["inventory-overview", scope] as const,
  inventoryAttention: (scope: string) => ["inventory-attention", scope] as const,
  inventoryItems: (scope: string, search: string, offset: number) =>
    ["inventory-items", scope, search, offset] as const,
  inventoryLocations: (scope: string) => ["inventory-locations", scope] as const,
  inventoryStock: (
    scope: string,
    locationId: string,
    search: string,
    status: string,
  ) => ["inventory-stock", scope, locationId, search, status] as const,
  inventoryMovements: (scope: string, locationId: string) =>
    ["inventory-movements", scope, locationId] as const,
  teamStock: (scope: string, teamId: string) =>
    ["team-stock", scope, teamId] as const,
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

export function assignmentSourceLabel(job: Job) {
  if (job.assignment_source === "auto") return "Auto-assigned";
  if (job.assignment_source === "manual") return "Manually assigned";
  if (job.assignment_source === "legacy") return "Existing assignment";
  return null;
}

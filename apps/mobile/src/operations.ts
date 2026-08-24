import type { Role } from "./capabilities";
import type { AvailabilitySlot, Job, ReportPoint } from "./lib";

export type MainTab = "today" | "jobs" | "team" | "reports" | "profile";
export const navigationTabs = (role: Role): MainTab[] =>
  role === "employee"
    ? ["today", "jobs", "profile"]
    : ["today", "jobs", "team", "reports", "profile"];
export const teamSections = () =>
  ["teams", "staff", "shifts", "attendance"] as const;
export const updateJobInList = (jobs: Job[], next: Job) =>
  jobs.map((job) => (job.id === next.id ? next : job));
export const nextOperationalJob = (jobs: Job[]) =>
  jobs.find((job) => !["completed", "cancelled"].includes(job.status));
export const attendanceElapsedMinutes = (clockIn: string, now = Date.now()) =>
  Math.max(0, Math.floor((now - Date.parse(clockIn)) / 60000));
export const needsActiveReassignmentConfirmation = (status: string) =>
  status === "en_route" || status === "in_progress";
export const reportMaximum = (series: ReportPoint[]) =>
  Math.max(1, ...series.map((point) => point.booked_sales_minor));
export const reportBarPercent = (value: number, maximum: number) =>
  Math.max(3, Math.min(100, (value / Math.max(1, maximum)) * 100));
export const offlineMessage = (cachedAt?: string) =>
  cachedAt
    ? `Offline · updated ${new Date(cachedAt).toLocaleTimeString()}`
    : "Offline · no cached jobs";
export const conflictMessage = (code: string) =>
  code === "TEAM_ASSIGNMENT_CONFLICT"
    ? "That team already has work during this appointment."
    : code === "LEAVE_HAS_ASSIGNED_WORK"
      ? "Reassign this employee's future work first."
      : "The server did not confirm this action.";
export const isIsoBookingDate = (value: string) =>
  /^\d{4}-\d{2}-\d{2}$/.test(value);
export const availabilityOptions = (slots: AvailabilitySlot[]) =>
  slots.flatMap((slot) =>
    slot.available
      ? slot.resources.map((resource) => ({ slot, resource }))
      : [],
  );
export const reschedulePayload = (holdToken: string) => ({
  hold_token: holdToken,
});

export type Role = "employee" | "manager" | "admin";

export function capabilities(role: Role) {
  const management = role === "manager" || role === "admin";
  return { canViewAssignedJobs: true, canRecordAssignedCash: true, canViewAllJobs: management, canAssignJobs: management, canManageCancellations: management, canReschedule: management, canViewReports: management, canViewTeam: management, canManageAnyJob: management };
}

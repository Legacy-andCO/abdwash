export type Role = "employee" | "manager" | "admin";

export function capabilities(role: Role) {
  const management = role === "manager" || role === "admin";
  return {
    canViewAssignedJobs: true,
    canRecordAssignedCash: true,
    canManageOwnProfile: true,
    canClockAttendance: true,
    canRequestLeave: true,
    canViewAllJobs: management,
    canAssignJobs: management,
    canManageCancellations: management,
    canReschedule: management,
    canViewReports: management,
    canViewTeam: management,
    canManageAnyJob: management,
    canManageStaff: management,
    canManageTeams: management,
    canManageShifts: management,
    canViewBusinessAttendance: management,
    canApproveLeave: management,
    canManageCustomers: management,
    canManageManagers: role === "admin",
  };
}

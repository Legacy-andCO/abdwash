import { describe, expect, it } from "vitest";
import { capabilities } from "./capabilities";

describe("staff capabilities", () => {
  it("keeps employees scoped to assigned work", () => {
    expect(capabilities("employee")).toMatchObject({ canViewAssignedJobs: true, canViewAllJobs: false, canAssignJobs: false, canViewReports: false });
  });
  it.each(["manager", "admin"] as const)("gives %s management capabilities", (role) => {
    expect(capabilities(role)).toMatchObject({ canViewAllJobs: true, canAssignJobs: true, canManageCancellations: true, canViewReports: true, canManageStaff: true, canApproveLeave: true });
  });
  it("reserves manager-account administration for admins", () => {
    expect(capabilities("manager").canManageManagers).toBe(false);
    expect(capabilities("admin").canManageManagers).toBe(true);
  });
});

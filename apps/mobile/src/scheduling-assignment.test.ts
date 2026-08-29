// @ts-expect-error Node built-ins are available to Vitest but intentionally absent from the Expo app tsconfig.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { capabilities } from "./capabilities";
import { assignmentSourceLabel, queryKeys } from "./cache/policy";
import type { Job } from "./lib";

const source = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

describe("smart scheduling assignment UI", () => {
  it("keeps assignment options scoped to the current operational identity", () => {
    expect(queryKeys.assignmentOptions("business:manager", "job-1")).toEqual([
      "assignment-options",
      "business:manager",
      "job-1",
    ]);
  });

  it("shows assignment provenance without exposing internal scores", () => {
    expect(assignmentSourceLabel({ assignment_source: "auto" } as Job)).toBe(
      "Auto-assigned",
    );
    expect(assignmentSourceLabel({ assignment_source: "manual" } as Job)).toBe(
      "Manually assigned",
    );
  });

  it("keeps assignment and turnaround override manager-only", () => {
    expect(capabilities("employee").canAssignJobs).toBe(false);
    expect(capabilities("manager").canAssignJobs).toBe(true);
    const jobsScreen = source("./screens/JobsScreen.tsx");
    expect(jobsScreen).toContain('title={mutation.isPending ? "Assigning…" : "Auto assign"}');
    expect(jobsScreen).toContain('selected?.status !== "turnaround_conflict"');
    expect(jobsScreen).toContain('text: "Assign anyway"');
    expect(jobsScreen).toContain('item.status === "time_conflict"');
  });

  it("patches targeted job caches after an authoritative assignment response", () => {
    const operations = source("./queries/operations.ts");
    expect(operations).toContain("updateJobCaches(client, scope, job)");
    expect(operations).toContain("queryKeys.assignmentOptions(scope, job.id)");
  });
});

import { describe, expect, it } from "vitest";
import type { Job } from "../lib";
import {
  assignmentLabel,
  assignmentSourceLabel,
  cacheTimes,
  operationalScope,
  queryKeys,
  replaceJobInResponse,
  shouldShowPagination,
} from "./policy";

const job = (id: string, status: string) => ({ id, status }) as Job;

describe("operations cache policy", () => {
  it("isolates users and filter combinations in structured keys", () => {
    const today = { view: "today", scope: "all", date: "2026-08-25" } as const;
    const history = { view: "history", scope: "all" } as const;
    expect(queryKeys.jobs("business:user-a", today)).not.toEqual(
      queryKeys.jobs("business:user-b", today),
    );
    expect(queryKeys.jobs("business:user-a", today)).not.toEqual(
      queryKeys.jobs("business:user-a", history),
    );
    expect(
      queryKeys.jobs("business:user-a", {
        view: "all",
        scope: "all",
        search: "Mohammed",
      }),
    ).not.toEqual(
      queryKeys.jobs("business:user-a", {
        view: "all",
        scope: "all",
        search: "Abdo",
      }),
    );
  });

  it("includes business, staff and authoritative role in every scope", () => {
    expect(
      operationalScope({
        business_id: "business",
        staff_id: "person",
        role: "manager",
      } as never),
    ).toBe("business:person:manager");
    expect(
      operationalScope({
        business_id: "business",
        staff_id: "person",
        role: "employee",
      } as never),
    ).toBe("business:person:employee");
  });

  it("keeps availability much fresher than static workforce data", () => {
    expect(cacheTimes.availability).toBeLessThan(cacheTimes.teams);
    expect(cacheTimes.jobs).toBeLessThan(cacheTimes.profile);
  });

  it("keys team detail and cancellations inside the authenticated scope", () => {
    expect(queryKeys.team("business:staff:manager", "team-1")).toEqual([
      "team",
      "business:staff:manager",
      "team-1",
    ]);
    expect(queryKeys.cancellations("business:staff:manager")).toEqual([
      "cancellations",
      "business:staff:manager",
    ]);
  });

  it("updates one authoritative job without replacing unrelated jobs", () => {
    const existing = {
      jobs: [job("one", "assigned"), job("two", "assigned")],
      next_offset: null,
    };
    const changed = job("one", "en_route");
    expect(replaceJobInResponse(existing, changed)).toEqual({
      jobs: [changed, existing.jobs[1]],
      next_offset: null,
    });
  });

  it("hides pagination for a single first page", () => {
    expect(shouldShowPagination(0, null)).toBe(false);
    expect(shouldShowPagination(50, null)).toBe(true);
    expect(shouldShowPagination(0, 50)).toBe(true);
  });

  it("never labels an assigned ID as unassigned when names are unavailable", () => {
    expect(
      assignmentLabel({
        assigned_team_id: "team-1",
        assigned_team_name: null,
        assigned_staff_id: null,
        assigned_staff_name: null,
      } as Job),
    ).toBe("ASSIGNED");
  });

  it("explains auto, manual and legacy assignment provenance", () => {
    expect(assignmentSourceLabel({ assignment_source: "auto" } as Job)).toBe(
      "Auto-assigned",
    );
    expect(assignmentSourceLabel({ assignment_source: "manual" } as Job)).toBe(
      "Manually assigned",
    );
    expect(assignmentSourceLabel({ assignment_source: "legacy" } as Job)).toBe(
      "Existing assignment",
    );
  });
});

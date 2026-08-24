import { describe, expect, it } from "vitest";
import type { Job } from "../lib";
import { cacheTimes, queryKeys, replaceJobInResponse } from "./policy";

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
  });

  it("keeps availability much fresher than static workforce data", () => {
    expect(cacheTimes.availability).toBeLessThan(cacheTimes.teams);
    expect(cacheTimes.jobs).toBeLessThan(cacheTimes.profile);
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
});

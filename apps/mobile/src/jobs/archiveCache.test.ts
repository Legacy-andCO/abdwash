import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import type { Job } from "../lib";
import { removeArchivedBookingFromCaches } from "./archiveCache";

describe("archive cache updates", () => {
  it("removes the booking from every cached list, calendar and dashboard without touching history or other scopes", async () => {
    const client = new QueryClient();
    const job = { id: "job-1", booking_id: "booking-1" } as Job;
    const other = { id: "job-2", booking_id: "booking-2" } as Job;
    for (const view of ["today", "history"]) {
      client.setQueryData(["jobs", "manager", view], { jobs: [job, other], next_offset: 50 });
    }
    client.setQueryData(["jobs", "other-business"], { jobs: [job] });
    client.setQueryData(["calendar", "manager"], { jobs: [{ job_id: job.id }, { job_id: other.id }] });
    client.setQueryData(["dashboard", "manager"], { active_jobs: [job, other], metrics: [] });
    client.setQueryData(["communications", "manager", job.id], ["history"]);
    await removeArchivedBookingFromCaches(client, "manager", job);
    for (const view of ["today", "history"]) {
      expect(client.getQueryData(["jobs", "manager", view])).toEqual({ jobs: [other], next_offset: 50 });
      expect(client.getQueryState(["jobs", "manager", view])?.isInvalidated).toBe(true);
    }
    expect(client.getQueryData(["calendar", "manager"])).toEqual({ jobs: [{ job_id: other.id }] });
    expect(client.getQueryData(["dashboard", "manager"])).toEqual({ active_jobs: [other], metrics: [] });
    expect(client.getQueryData(["jobs", "other-business"])).toEqual({ jobs: [job] });
    expect(client.getQueryData(["communications", "manager", job.id])).toEqual(["history"]);
    client.clear();
  });
});

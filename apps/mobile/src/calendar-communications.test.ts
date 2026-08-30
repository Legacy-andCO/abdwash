// @ts-expect-error Node built-ins are available to Vitest but intentionally absent from the Expo app tsconfig.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

describe("calendar and customer communications integration", () => {
  it("uses a scoped persisted month-range cache key", () => {
    const policy = source("./cache/policy.ts");
    const queries = source("./queries/operations.ts");
    expect(policy).toContain('["calendar", scope, start, end]');
    expect(queries).toContain("persistedQueryMeta(retentionTimes.calendar)");
    expect(queries).toContain('findAll({ queryKey: ["calendar", scope] })');
  });

  it("shows at most three compact day entries and a more count", () => {
    const calendar = source("./components/OperationsCalendar.tsx");
    expect(calendar).toContain("dayJobs.slice(0, 3)");
    expect(calendar).toContain("dayJobs.length - 3");
    expect(calendar).toContain("onOpenJob(job.job_id)");
  });

  it("keeps cached calendar and communication data visible while refreshing", () => {
    const calendar = source("./components/OperationsCalendar.tsx");
    const jobs = source("./screens/JobsScreen.tsx");
    expect(calendar).toContain("query.isError && jobs.length");
    expect(jobs).toContain("communications.isFetching && communications.data?.length");
  });

  it("offers manager delay choices without changing the schedule", () => {
    const jobs = source("./screens/JobsScreen.tsx");
    const api = source("./lib.ts");
    expect(jobs).toContain("[15, 30, 45, 60]");
    expect(jobs).toContain("It does not change the appointment time");
    expect(api).toContain("/notifications/delay");
  });
});

import { describe, expect, it } from "vitest";
import { apiDurationMs, apiRouteTemplate } from "./apiPerformance";

describe("safe API performance diagnostics", () => {
  it("removes query values and identifiers from the logged route", () => {
    expect(
      apiRouteTemplate(
        "/api/v1/staff/jobs/6ba7b810-9dad-41d1-80b4-00c04fd430c8?search=Mohammed",
      ),
    ).toBe("/api/v1/staff/jobs/:id");
  });

  it("reports a bounded non-negative elapsed duration", () => {
    expect(apiDurationMs(100, 145)).toBe(45);
    expect(apiDurationMs(145, 100)).toBe(0);
  });
});

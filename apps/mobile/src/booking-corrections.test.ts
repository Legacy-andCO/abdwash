import { afterEach, describe, expect, it } from "vitest";
import { chartAxis, reportChartData } from "./reports/chartData";
import { getStaffLanguage, setStaffLanguage, t } from "./i18n";
import { staffArabic } from "./staff-translations";
import { formatWallClockTime } from "./time/uaeTime";
import { ApiError, domainErrorMessage } from "./errors/domainErrors";
const point = { date: "2026-01-02", booked_sales_minor: 12500, collected_revenue_minor: 5000, jobs: 3, completed: 1, cancelled: 1 };
afterEach(() => setStaffLanguage("en"));
describe("report chart values", () => {
  it("fills missing days without inventing money or jobs", () => {
    const points = reportChartData([point], "2026-01-01", "2026-01-03");
    expect(points).toHaveLength(3);
    expect(points[0].jobs).toBe(0);
    expect(points[1]).toMatchObject(point);
    expect(points[2].collected_revenue_minor).toBe(0);
  });
  it("groups weeks and months consistently and preserves totals", () => {
    for (const end of ["2026-02-28", "2026-06-30"]) {
      const points = reportChartData([point, { ...point, date: end }], "2026-01-01", end);
      expect(points.reduce((sum, p) => sum + p.booked_sales_minor, 0)).toBe(25000);
      expect(points.reduce((sum, p) => sum + p.jobs, 0)).toBe(6);
      expect(points.at(-1)?.endDate).toBe(end);
    }
  });
  it("uses integer count ticks and a nonzero scale for an empty chart", () => {
    for (const maximum of [0, 1, 7, 130]) {
      const axis = chartAxis(maximum, true);
      expect(axis.maximum).toBeGreaterThanOrEqual(maximum);
      expect(axis.ticks.every(Number.isInteger)).toBe(true);
    }
    expect(reportChartData([], "bad", "bad")).toEqual([]);
  });
});
describe("staff language", () => {
  it("keeps interpolation values intact and switches interface text independently", () => {
    expect(t("Double-book this time?" )).toBe("Double-book this time?");
    setStaffLanguage("ar");
    expect(getStaffLanguage()).toBe("ar");
    expect(t("Double-book this time?" )).toMatch(/[\u0600-\u06ff]/);
    expect(t("Double-book this time · {p0}", { p0: "09:00" })).toContain("09:00");
    expect(formatWallClockTime("09:00")).not.toMatch(/AM|PM/);
    setStaffLanguage("en");
    expect(t("Confirm cancellation")).toBe("Confirm cancellation");
  });
  it("preserves every placeholder in the Arabic catalogue", () => {
    for (const [en, ar] of Object.entries(staffArabic)) {
      expect(ar.match(/\{\w+\}/g)?.sort() ?? [], en).toEqual(en.match(/\{\w+\}/g)?.sort() ?? []);
    }
  });
  it("localizes domain errors and does not leak unknown English server messages", () => {
    setStaffLanguage("ar");
    expect(domainErrorMessage(new ApiError("STALE_JOB_VERSION", 409), "Unable to book")).toMatch(/[\u0600-\u06ff]/);
    expect(domainErrorMessage(new ApiError("NEW_SERVER_ERROR", 409, "Untranslated server message"), "Cancel booking")).toBe(t("Cancel booking"));
  });
});

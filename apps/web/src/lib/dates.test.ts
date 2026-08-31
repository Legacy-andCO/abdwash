import { describe, expect, it } from "vitest";
import {
  calendarCells,
  dateKey,
  formatMoney,
  formatSchedule,
  todayInTimezone,
  TRIFECTA_TIME_ZONE,
} from "./dates";

describe("date and display helpers", () => {
  it("uses the business timezone when determining today", () => {
    expect(todayInTimezone("Asia/Dubai", new Date("2030-01-01T21:00:00Z"))).toBe("2030-01-02");
  });
  it("creates stable API date keys", () => expect(dateKey(2030, 0, 7)).toBe("2030-01-07"));
  it("aligns a month on its correct weekday", () => expect(calendarCells(2030, 0)[0]).toBeNull());
  it("formats minor currency units", () => expect(formatMoney(12500, "AED")).toContain("125"));
  it("renders the authoritative start and end window", () => {
    const result = formatSchedule(
      "2026-08-31T06:00:00Z",
      "2026-08-31T08:00:00Z",
      TRIFECTA_TIME_ZONE,
      "en-GB",
    );
    expect(result).toContain("10:00–12:00");
  });
});

import { describe, expect, it } from "vitest";
import { hourlyQuickTimes } from "./exactTime";

describe("manager exact-time rescheduling", () => {
  it("builds hourly quick choices within configured business hours", () => {
    expect(hourlyQuickTimes("08:30:00", "12:30:00")).toEqual([
      "09:00",
      "10:00",
      "11:00",
      "12:00",
    ]);
  });

  it("returns no quick choices for a closed or invalid configuration", () => {
    expect(hourlyQuickTimes(null, null)).toEqual([]);
    expect(hourlyQuickTimes("invalid", "18:00:00")).toEqual([]);
  });

  it("omits quick times whose full service duration crosses closing", () => {
    expect(hourlyQuickTimes("09:00", "13:00", 120)).toEqual([
      "09:00",
      "10:00",
      "11:00",
    ]);
  });
});

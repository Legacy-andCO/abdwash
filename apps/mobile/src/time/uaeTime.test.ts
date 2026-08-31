import { describe, expect, it } from "vitest";
import {
  addUaeDays,
  formatUaeTime,
  uaeAppointmentParts,
  uaeDateKey,
} from "./uaeTime";

describe("UAE operational time", () => {
  it("groups an after-midnight UAE appointment under the UAE date", () => {
    expect(uaeDateKey("2026-08-30T20:30:00Z")).toBe("2026-08-31");
  });

  it.each([
    ["2026-08-31T06:00:00Z", "10:00"],
    ["2026-08-31T18:30:00Z", "22:30"],
  ])("formats %s as the correct UAE wall time", (stored, expected) => {
    expect(uaeAppointmentParts(stored).time).toBe(expected);
    expect(formatUaeTime(stored, "en-GB")).toBe(expected);
  });

  it("keeps date arithmetic independent from the test runner timezone", () => {
    expect(addUaeDays("2026-08-31", 1)).toBe("2026-09-01");
    expect(addUaeDays("2026-08-31", -1)).toBe("2026-08-30");
  });
});

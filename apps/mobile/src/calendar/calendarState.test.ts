import { describe, expect, it } from "vitest";
import { calendarDays, jobsByDate, monthWindow, shiftMonth } from "./calendarState";
import type { CalendarJob } from "../lib";

const job = (id: string, date: string, hour: number): CalendarJob => ({
  job_id: id,
  scheduled_start: `${date}T${String(hour).padStart(2, "0")}:00:00Z`,
  scheduled_end: `${date}T${String(hour + 1).padStart(2, "0")}:00:00Z`,
  local_date: date,
  status: "assigned",
  team_id: "team-1",
  team_short_name: "Team 1",
  vehicle_label: "Toyota Camry",
  service_label: "Standard Wash",
});

describe("operations calendar state", () => {
  it("creates a bounded traditional month grid", () => {
    const range = monthWindow("2026-08");
    const days = calendarDays(range.start, range.end);
    expect(days.length).toBeLessThanOrEqual(42);
    expect(days).toContain("2026-08-01");
    expect(days).toContain("2026-08-31");
  });

  it("moves between months without changing job state", () => {
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
    expect(shiftMonth("2026-12", 1)).toBe("2027-01");
  });

  it("groups and sorts the date agenda chronologically", () => {
    const grouped = jobsByDate([
      job("late", "2026-08-30", 14),
      job("early", "2026-08-30", 9),
    ]);
    expect(grouped.get("2026-08-30")?.map((item) => item.job_id)).toEqual([
      "early",
      "late",
    ]);
  });
});

import { describe, expect, it } from "vitest";
import type { Job, ReportPoint } from "./lib";
import {
  attendanceElapsedMinutes,
  availabilityOptions,
  conflictMessage,
  navigationTabs,
  needsActiveReassignmentConfirmation,
  nextOperationalJob,
  offlineMessage,
  isIsoBookingDate,
  reportBarPercent,
  reportMaximum,
  reschedulePayload,
  teamSections,
  updateJobInList,
} from "./operations";

const job = (id: string, status: string): Job => ({
  id,
  status,
  booking_id: id,
  booking_reference: id,
  assigned_staff_id: null,
  assigned_staff_name: null,
  assigned_team_id: null,
  assigned_team_name: null,
  scheduled_start: "2026-08-24T09:00:00Z",
  scheduled_end: "2026-08-24T11:00:00Z",
  en_route_at: null,
  estimated_arrival_at: null,
  started_at: null,
  completed_at: null,
  customer_name: "Customer",
  customer_phone: "+971501234567",
  written_address: "Abu Dhabi",
  location_url: "https://www.google.com/maps",
  latitude: null,
  longitude: null,
  location_instructions: null,
  payment_status: "unpaid",
  payment_method: null,
  total_amount_minor: 10000,
  currency_code: "AED",
  vehicles: [],
  timeline: [],
});

describe("reschedule data flow", () => {
  it("validates dates and keeps each date in a separate availability key", () => {
    expect(isIsoBookingDate("2026-08-25")).toBe(true);
    expect(isIsoBookingDate("25/08/2026")).toBe(false);
  });
  it("shows only real resource choices", () => {
    const slots = [
      {
        available: true,
        resources: [{ resource_id: "team-1", resource_name: "Mobile Team 1" }],
      },
      {
        available: false,
        resources: [{ resource_id: "team-2", resource_name: "Mobile Team 2" }],
      },
    ] as never;
    expect(availabilityOptions(slots)).toHaveLength(1);
  });
  it("sends only the backend-supported hold token", () => {
    expect(reschedulePayload("token")).toEqual({ hold_token: "token" });
  });
});

describe("operations navigation and permissions", () => {
  it("keeps employee navigation focused", () => {
    expect(navigationTabs("employee")).toEqual(["today", "jobs", "profile"]);
  });
  it.each(["manager", "admin"] as const)(
    "gives %s five management tabs",
    (role) => {
      expect(navigationTabs(role)).toEqual([
        "today",
        "jobs",
        "team",
        "reports",
        "profile",
      ]);
    },
  );
  it("keeps workforce features nested under Team", () => {
    expect(teamSections()).toEqual(["teams", "staff", "shifts", "attendance"]);
  });
});

describe("authoritative operation responses", () => {
  it("updates one job without globally reloading the list", () => {
    const current = [job("one", "assigned"), job("two", "assigned")];
    const changed = job("one", "en_route");
    expect(updateJobInList(current, changed)).toEqual([changed, current[1]]);
  });
  it("chooses the next incomplete employee job", () => {
    expect(
      nextOperationalJob([job("one", "completed"), job("two", "assigned")])?.id,
    ).toBe("two");
  });
  it.each(["en_route", "in_progress"])(
    "requires confirmation for %s reassignment",
    (status) => {
      expect(needsActiveReassignmentConfirmation(status)).toBe(true);
    },
  );
  it("does not require active confirmation for upcoming work", () => {
    expect(needsActiveReassignmentConfirmation("assigned")).toBe(false);
  });
});

describe("attendance, reports and resilient states", () => {
  it("calculates a client display timer without persisting ticks", () => {
    expect(
      attendanceElapsedMinutes(
        "2026-08-24T09:00:00Z",
        Date.parse("2026-08-24T10:15:00Z"),
      ),
    ).toBe(75);
  });
  it("bounds graph bars and handles an empty series", () => {
    expect(reportMaximum([])).toBe(1);
    expect(reportBarPercent(0, 100)).toBe(3);
    expect(reportBarPercent(200, 100)).toBe(100);
  });
  it("uses aggregated report values", () => {
    const points = [
      { booked_sales_minor: 200 },
      { booked_sales_minor: 500 },
    ] as ReportPoint[];
    expect(reportMaximum(points)).toBe(500);
  });
  it("distinguishes cached and empty offline reads", () => {
    expect(offlineMessage()).toContain("no cached jobs");
    expect(offlineMessage("2026-08-24T09:00:00Z")).toContain("updated");
  });
  it("turns server conflict codes into useful messages", () => {
    expect(conflictMessage("TEAM_ASSIGNMENT_CONFLICT")).toContain(
      "already has work",
    );
    expect(conflictMessage("LEAVE_HAS_ASSIGNED_WORK")).toContain("Reassign");
    expect(conflictMessage("OFFLINE")).toContain("server did not confirm");
  });
});

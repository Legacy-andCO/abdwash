import { describe, expect, it } from "vitest";
import type { JobChecklistItem, JobQuality } from "../lib";
import {
  availablePhotoCategories,
  qualitySummary,
  qualityWritesDisabled,
  toggledChecklist,
} from "./qualityState";

const item = (id: string, completed: boolean): JobChecklistItem => ({
  id,
  label: id,
  is_required: true,
  position: 1,
  completed_at: completed ? "2026-08-27T10:00:00Z" : null,
  completed_by_staff_id: completed ? "staff" : null,
  completed_by_staff_name: completed ? "Ahmed" : null,
});

describe("job quality mobile state", () => {
  it("builds the concise completion summary", () => {
    const quality = {
      required_completed: 6,
      required_total: 8,
      before_photo_count: 4,
      after_photo_count: 5,
      issue_count: 1,
    } as JobQuality;
    expect(qualitySummary(quality)).toEqual({
      checklist: "6/8",
      before: 4,
      after: 5,
      issues: 1,
    });
  });

  it("sends the authoritative state of the whole checklist after a tap", () => {
    expect(
      toggledChecklist([item("one", true), item("two", false)], "two"),
    ).toEqual([
      { id: "one", completed: true },
      { id: "two", completed: true },
    ]);
  });

  it("limits photo categories by operational state", () => {
    expect(availablePhotoCategories("arrived")).toEqual(["before", "damage"]);
    expect(availablePhotoCategories("in_progress")).toContain("after");
    expect(availablePhotoCategories("completed")).toEqual([]);
  });

  it("disables quality writes only when connectivity is known to be offline", () => {
    expect(qualityWritesDisabled(false)).toBe(true);
    expect(qualityWritesDisabled(true)).toBe(false);
    expect(qualityWritesDisabled(null)).toBe(false);
  });
});

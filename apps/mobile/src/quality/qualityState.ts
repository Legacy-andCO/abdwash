import type { JobChecklistItem, JobPhoto, JobQuality } from "../lib";

export function qualitySummary(quality: JobQuality) {
  return {
    checklist: `${quality.required_completed}/${quality.required_total}`,
    before: quality.before_photo_count,
    after: quality.after_photo_count,
    issues: quality.issue_count,
  };
}

export function toggledChecklist(items: JobChecklistItem[], itemId: string) {
  return items.map((item) => ({
    id: item.id,
    completed:
      item.id === itemId
        ? item.completed_at === null
        : item.completed_at !== null,
  }));
}

export function availablePhotoCategories(
  status: string,
): JobPhoto["category"][] {
  if (status === "arrived") return ["before", "damage"];
  if (status === "in_progress") return ["before", "after", "damage", "issue"];
  return [];
}

export const qualityWritesDisabled = (isConnected: boolean | null) =>
  isConnected === false;

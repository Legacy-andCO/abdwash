import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

describe("job quality mobile contracts", () => {
  it("opens the picker on demand and retains only failed previews for retry", () => {
    const quality = source("./components/JobQualityControls.tsx");
    const chooseStart = quality.indexOf("async function choosePhoto");
    const uploadStart = quality.indexOf("async function uploadDrafts");
    const inspectionStart = quality.indexOf("async function saveInspection");
    const uploadFlow = quality.slice(uploadStart, inspectionStart);
    expect(chooseStart).toBeGreaterThan(0);
    expect(quality.indexOf("requestCameraPermissionsAsync", chooseStart)).toBeGreaterThan(
      chooseStart,
    );
    expect(quality).toContain("allowsMultipleSelection: true");
    expect(uploadFlow).toContain("await photo.mutateAsync(draft)");
    expect(uploadFlow).toContain("items.filter((item) => item.clientRequestId !== draft.clientRequestId)");
    expect(uploadFlow).toContain("items.map((item) => item.clientRequestId === draft.clientRequestId");
  });

  it("renders inspection, checklist, issue, evidence, and summary controls", () => {
    const quality = source("./components/JobQualityControls.tsx");
    expect(quality).toContain("Vehicle inspection");
    expect(quality).toContain("Service checklist");
    expect(quality).toContain("Report an issue");
    expect(quality).toContain("Photo evidence");
    expect(quality).toContain('<Summary label={t("Checklist")}');
    expect(quality).toContain("qualityWritesDisabled");
  });

  it("formats quality history in the staff language and Abu Dhabi time", () => {
    const quality = source("./components/JobQualityControls.tsx");
    expect(quality).toContain("formatUaeDateTime(quality.inspection.completed_at)");
    expect(quality).toContain("formatUaeDateTime(item.created_at)");
  });

  it("shows manager complaint decisions and correction scheduling", () => {
    const quality = source("./components/JobQualityControls.tsx");
    expect(quality).toContain("Customer complaints");
    expect(quality).toContain('decision="under_review"');
    expect(quality).toContain('decision="resolved"');
    expect(quality).toContain('decision="rejected"');
    expect(quality).toContain("Approve and schedule rewash");
  });

  it("connects backend completion authority and a scoped persisted quality query", () => {
    const jobs = source("./screens/JobsScreen.tsx");
    const queries = source("./queries/operations.ts");
    expect(jobs).toContain("useJobQualityQuery");
    expect(jobs).toContain("qualityQuery.data?.can_complete === false");
    expect(queries).toContain("queryKeys.quality(scope, jobId)");
    expect(queries).toContain("persistedQueryMeta(retentionTimes.quality)");
  });

  it("keeps cached quality visible when a refresh fails", () => {
    const quality = source("./components/JobQualityControls.tsx");
    expect(quality).toContain("Vehicle condition record couldn't be refreshed");
    expect(quality).toContain("The last saved details remain visible.");
    expect(quality).toContain("Vehicle condition record couldn't be loaded");
  });
});

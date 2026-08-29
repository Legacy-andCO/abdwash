import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

describe("catalogue pricing booking UI", () => {
  it("submits add-on ids through the existing booking vehicle payload", () => {
    const state = source("./booking-state.ts");
    const wizard = source("../components/booking-wizard.tsx");
    expect(state).toContain('type: "toggle_addon"');
    expect(wizard).toContain('type: "toggle_addon"');
    expect(wizard).toContain("addon_ids");
  });

  it("uses translated add-on and mobile-minimum customer messages", () => {
    const wizard = source("../components/booking-wizard.tsx");
    const translations = source("./i18n.ts");
    expect(wizard).toContain('t("booking.vehicles.addons")');
    expect(wizard).toContain('t("booking.review.mobileMinimum")');
    expect(translations).toContain('"booking.vehicles.addons"');
    expect(translations).toContain('"booking.review.mobileMinimum"');
  });
});

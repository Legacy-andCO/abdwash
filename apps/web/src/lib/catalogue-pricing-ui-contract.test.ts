import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

describe("catalogue pricing booking UI", () => {
  it("uses a vehicle-first booking sequence and keeps backend catalogue pricing authoritative", () => {
    const state = source("./booking-state.ts");
    const wizard = source("../components/booking-wizard.tsx");
    expect(state.indexOf('"vehicles"')).toBeLessThan(state.indexOf('"service"'));
    expect(state.indexOf('"service"')).toBeLessThan(state.indexOf('"details"'));
    expect(wizard).toContain("service.prices?.find");
    expect(wizard).toContain("service.customer_bookable !== false");
  });

  it("keeps the desktop matrix and uses catalogue-driven cards on phones", () => {
    const preview = source("../components/services-preview.tsx");
    expect(preview).toContain('type PricingClass = "car" | "suv"');
    expect(preview).toContain('pricingClass === "car" ? "sedan" : "suv"');
    expect(preview).toContain('<table className="service-comparison">');
    expect(preview).toContain("service.included_features");
    expect(preview).toContain("localizeServiceFeature");
    expect(preview).toContain('className="service-comparison-mobile"');
    expect(preview).toContain("serviceFeatureAdditions(service, previous)");
    expect(preview).toContain("service.included_features ?? []");
    expect(preview).not.toContain('overflowX: "auto"');
    const styles = source("../app/globals.css");
    expect(styles).toContain(".service-comparison-desktop");
    expect(styles).toContain(".service-comparison-mobile");
    expect(styles).toContain("@media (max-width: 700px)");
  });

  it("keeps the monthly package visible without booking it as one ordinary wash", () => {
    const preview = source("../components/services-preview.tsx");
    expect(preview).toContain("service.customer_bookable !== false");
    expect(preview).toContain('t("services.packageUnavailable")');
  });

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

// @ts-expect-error Node built-ins are available to Vitest but intentionally absent from the Expo app tsconfig.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { cacheTimes, queryKeys } from "./cache/policy";

const source = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

describe("services and pricing management", () => {
  it("uses tenant-scoped cached catalogue, settings and template resources", () => {
    expect(queryKeys.managedCatalogue("business:staff:manager")).toEqual([
      "managed-catalogue",
      "business:staff:manager",
    ]);
    expect(queryKeys.businessSettings("business:staff:manager")[0]).toBe(
      "business-settings",
    );
    expect(queryKeys.serviceTemplate("scope", "service")).toEqual([
      "service-template",
      "scope",
      "service",
    ]);
    expect(cacheTimes.catalogue).toBeGreaterThan(0);
  });

  it("exposes catalogue management only through the manager entry point", () => {
    const today = source("./screens/TodayScreen.tsx");
    const shell = source("./navigation/OperationsShell.tsx");
    expect(today).toContain("{management ? (");
    expect(today).toContain('title="Services & pricing"');
    expect(shell).toContain("<ServicesPricingScreen");
  });

  it("supports mobile service prices, durations, add-ons and lifecycle", () => {
    const screen = source("./screens/ServicesPricingScreen.tsx");
    expect(screen).toContain("VEHICLE PRICING");
    expect(screen).toContain("default_duration_minutes");
    expect(screen).toContain("mobile_available");
    expect(screen).toContain("shop_available");
    expect(screen).toContain("Customer bookings are mobile service only.");
    expect(screen).not.toContain('label="Shop service"');
    expect(screen).not.toContain('label="Available at shop"');
    expect(screen).toContain('title="Add add-on"');
    expect(screen).toContain('"Deactivate service"');
  });

  it("describes consumption templates as completion-time expected usage", () => {
    const screen = source("./screens/ServicesPricingScreen.tsx");
    expect(screen).toContain(
      "Expected usage per completed service",
    );
    expect(screen).toContain("estimates, not exact physical usage");
    expect(screen).toContain('action: "update_template"');
  });

  it("loads settings and consumables only for their visible context", () => {
    const screen = source("./screens/ServicesPricingScreen.tsx");
    expect(screen).toContain('management && tab === "settings"');
    expect(screen).toContain("useServiceTemplateQuery(context, serviceId");
  });

  it("supports manager-owned invoice identity and VAT configuration", () => {
    const screen = source("./screens/ServicesPricingScreen.tsx");
    expect(screen).toContain("INVOICE IDENTITY");
    expect(screen).toContain('label="VAT registered"');
    expect(screen).toContain('label="Tax registration number (TRN)"');
    expect(screen).toContain('label="Catalogue prices include VAT"');
  });

  it("captures supplier evidence metadata without calling the voucher a tax invoice", () => {
    const finance = source("./screens/FinanceScreen.tsx");
    expect(finance).toContain("supplier_document_number");
    expect(finance).toContain("supplier_tax_registration_number");
    expect(finance).toContain("evidence_status");
    expect(finance).toContain("Attach receipt photo");
    expect(finance).toContain("uploadExpenseEvidence");
    expect(finance).not.toContain("Supplier Tax Invoice");
  });
});

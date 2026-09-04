// @ts-expect-error Node built-ins are available to Vitest but intentionally absent from Expo.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

describe("manager coupon controls", () => {
  const screen = source("./screens/CouponManager.tsx");
  const catalogue = source("./screens/ServicesPricingScreen.tsx");
  const api = source("./lib.ts");
  const queries = source("./queries/operations.ts");
  const capabilities = source("./capabilities.ts");

  it("adds coupons to the existing manager-only catalogue shell", () => {
    expect(catalogue).toContain('type ManagementTab = "services" | "coupons"');
    expect(catalogue).toContain("<CouponManager");
    expect(capabilities).toContain("canManageCoupons: management");
  });

  it("supports list, create, edit, and active state changes", () => {
    expect(screen).toContain('title="Create coupon"');
    expect(screen).toContain('editing === "new"');
    expect(screen).toContain('action: "update"');
    expect(screen).toContain("setActive");
    expect(screen).toContain("<StatusChip");
  });

  it("selects canonical catalogue services and vehicle types by identifier", () => {
    expect(screen).toContain("catalogue?.vehicle_types");
    expect(screen).toContain("catalogue?.services");
    expect(screen).toContain("service_ids: [...serviceIds]");
    expect(screen).toContain("vehicle_types: [...vehicleTypes]");
  });

  it("validates code, percentage, and optional minimum before submission", () => {
    expect(screen).toContain("/^[A-Z0-9]{3,6}$/");
    expect(screen).toContain("percentage >= 1");
    expect(screen).toContain("percentage <= 100");
    expect(screen).toContain("minimum_vehicle_count: minimumCount");
    expect(screen).toContain("disabled={!valid}");
  });

  it("uses protected staff endpoints and refreshes the coupon cache", () => {
    expect(api).toContain('api<CouponList>("/api/v1/staff/coupons")');
    expect(api).toContain('json("POST", body)');
    expect(api).toContain('json("PATCH", body)');
    expect(queries).toContain("queryKeys.coupons(scope)");
    expect(queries).toContain("invalidateQueries");
  });
});

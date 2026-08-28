import { describe, expect, it } from "vitest";

import {
  canConfirmCashHandover,
  cashDifference,
  cashDifferenceLabel,
  expenseAmountMinor,
  expenseCategories,
} from "./financeState";
import { navigationTabs } from "../operations";

describe("finance input rules", () => {
  it("keeps expense amounts in integer minor units", () => {
    expect(expenseAmountMinor("180.25")).toBe(18_025);
    expect(expenseAmountMinor("0")).toBeNull();
    expect(expenseAmountMinor("-1")).toBeNull();
    expect(expenseAmountMinor("not money")).toBeNull();
  });

  it("provides the complete expense category contract", () => {
    expect(expenseCategories).toContain("fuel");
    expect(expenseCategories).toContain("chemicals_supplies");
    expect(new Set(expenseCategories).size).toBe(expenseCategories.length);
  });

  it("classifies exact, short and over cash without using tender", () => {
    expect(cashDifference(63_000, 63_000)).toBe(0);
    expect(cashDifferenceLabel(cashDifference(63_000, 60_000))).toBe("short");
    expect(cashDifferenceLabel(cashDifference(63_000, 65_000))).toBe("over");
  });

  it("requires a note only for a discrepancy", () => {
    expect(canConfirmCashHandover(3, 63_000, 0, "")).toBe(true);
    expect(canConfirmCashHandover(3, 60_000, -3_000, "")).toBe(false);
    expect(canConfirmCashHandover(3, 60_000, -3_000, "Count checked")).toBe(true);
    expect(canConfirmCashHandover(0, 0, 0, "")).toBe(false);
  });

  it("keeps the reports/finance destination manager-only", () => {
    expect(navigationTabs("manager")).toContain("reports");
    expect(navigationTabs("admin")).toContain("reports");
    expect(navigationTabs("employee")).not.toContain("reports");
  });
});

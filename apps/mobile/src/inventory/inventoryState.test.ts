import { describe, expect, it } from "vitest";
import {
  inventoryCategories,
  getInventoryActionValidation,
  inventoryStatus,
  inventoryUnits,
  managementInventoryActions,
  validQuantity,
} from "./inventoryState";

describe("inventory domain UI", () => {
  it("uses the controlled backend categories and units", () => {
    expect(inventoryCategories).toContain("chemicals");
    expect(inventoryCategories).toContain("equipment_consumables");
    expect(inventoryUnits).toEqual(
      expect.arrayContaining(["piece", "liter", "milliliter", "pack"]),
    );
  });

  it("derives normal, low, and out without persisted client state", () => {
    expect(inventoryStatus(4, 3)).toBe("normal");
    expect(inventoryStatus(3, 3)).toBe("low");
    expect(inventoryStatus(0, 3)).toBe("out");
  });

  it("keeps employees on usage while managers receive all controls", () => {
    expect(managementInventoryActions("employee")).toEqual(["usage"]);
    expect(managementInventoryActions("manager")).toContain("stock_count");
  });

  it("rejects negative and non-numeric physical quantities", () => {
    expect(validQuantity("0.250")).toBe(true);
    expect(validQuantity("0")).toBe(false);
    expect(validQuantity("-1")).toBe(false);
    expect(validQuantity("not a number")).toBe(false);
    expect(validQuantity("0", true)).toBe(true);
  });

  const validStockInput = {
    name: "",
    threshold: "0",
    itemId: "item-1",
    locationId: "main-shop",
    destinationId: "van-1",
    hasQuantityLine: true,
    reason: "Physical count",
    jobId: "job-1",
    expenseAmount: "",
    isEmployee: false,
  };

  it("enables receive, stock count, and wastage with their real requirements", () => {
    expect(getInventoryActionValidation("receive", validStockInput).canSubmit).toBe(true);
    expect(getInventoryActionValidation("stock_count", validStockInput).canSubmit).toBe(true);
    expect(getInventoryActionValidation("wastage", validStockInput).canSubmit).toBe(true);
  });

  it("explains missing location, quantity, reason, and transfer destination", () => {
    expect(
      getInventoryActionValidation("receive", {
        ...validStockInput,
        locationId: "",
      }).reason,
    ).toBe("Select a stock location.");
    expect(
      getInventoryActionValidation("receive", {
        ...validStockInput,
        hasQuantityLine: false,
      }).reason,
    ).toBe("Enter a quantity greater than zero.");
    expect(
      getInventoryActionValidation("wastage", {
        ...validStockInput,
        reason: "",
      }).reason,
    ).toBe("Enter a reason.");
    expect(
      getInventoryActionValidation("transfer", {
        ...validStockInput,
        destinationId: "main-shop",
      }).reason,
    ).toBe("Source and destination must be different.");
  });

  it("requires an assigned job for employee usage", () => {
    expect(
      getInventoryActionValidation("usage", {
        ...validStockInput,
        isEmployee: true,
        jobId: "",
      }).reason,
    ).toBe("Enter the assigned job ID.");
  });
});

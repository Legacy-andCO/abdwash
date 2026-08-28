import { describe, expect, it } from "vitest";
import {
  inventoryCategories,
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
});

import { describe, expect, it } from "vitest";
import { normalizeCustomerSearch } from "./customerSearch";

describe("customer name search", () => {
  it("trims and collapses whitespace without changing the entered name", () => {
    expect(normalizeCustomerSearch("  Mohammed   Abdo ")).toBe("Mohammed Abdo");
  });
});

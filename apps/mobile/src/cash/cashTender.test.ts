import { describe, expect, it } from "vitest";

import {
  calculateCashTender,
  minorToInput,
  parseMoneyToMinor,
} from "./cashTender";

describe("cash tender", () => {
  it.each([
    ["86", 8_600],
    ["86.00", 8_600],
    ["100", 10_000],
    ["200.5", 20_050],
  ])("parses %s using exact minor units", (input, expected) => {
    expect(parseMoneyToMinor(input)).toBe(expected);
  });

  it("rejects malformed precision instead of rounding floats", () => {
    expect(parseMoneyToMinor("86.001")).toBeNull();
    expect(parseMoneyToMinor("abc")).toBeNull();
  });

  it("blocks underpayment and calculates exact change", () => {
    expect(calculateCashTender(8_600, "85")).toMatchObject({
      valid: false,
      error: "Amount received is less than the amount due.",
    });
    expect(calculateCashTender(8_600, "100")).toEqual({
      tenderedMinor: 10_000,
      changeMinor: 1_400,
      valid: true,
      error: null,
    });
    expect(minorToInput(8_605)).toBe("86.05");
  });
});

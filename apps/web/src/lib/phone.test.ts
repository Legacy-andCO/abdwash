import { describe, expect, it } from "vitest";
import { formatPhoneInput, normalizePhone } from "./phone";

describe("phone handling", () => {
  it("normalizes a UAE local mobile number", () => {
    expect(normalizePhone("050 123 4567", "AE")).toBe("+971501234567");
  });

  it("accepts an international UAE number", () => {
    expect(normalizePhone("+971 50 123 4567", "AE")).toBe("+971501234567");
  });

  it("accepts spaces and dashes", () => {
    expect(normalizePhone("050-123-4567", "AE")).toBe("+971501234567");
  });

  it("accepts valid non-UAE numbers", () => {
    expect(normalizePhone("+44 20 7946 0958", "AE")).toBe("+442079460958");
  });

  it("rejects impossible numbers", () => {
    expect(normalizePhone("123456789", "AE")).toBeNull();
  });

  it("rejects too-short numbers", () => {
    expect(normalizePhone("05012", "AE")).toBeNull();
  });

  it("formats naturally while typing", () => {
    expect(formatPhoneInput("0501234567", "AE")).toBe("050 123 4567");
  });
});

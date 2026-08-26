import { describe, expect, it } from "vitest";
import { validatePasswordConfirmation } from "./password";

describe("staff password confirmation", () => {
  it("accepts matching passwords that meet the minimum", () => {
    expect(validatePasswordConfirmation("Secure-123!", "Secure-123!")).toBeNull();
  });

  it("rejects short and mismatched passwords", () => {
    expect(validatePasswordConfirmation("short", "short")).toContain(
      "at least 8",
    );
    expect(validatePasswordConfirmation("Secure-123!", "Different-123!")).toBe(
      "Passwords do not match.",
    );
  });
});

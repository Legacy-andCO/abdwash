import { describe, expect, it } from "vitest";
import { getAuthConfirmUrl, safeReturnPath } from "./site-url";

describe("trusted authentication redirects", () => {
  it("preserves a local return path and rejects external or protocol-relative paths", () => {
    expect(safeReturnPath("/book?service=123")).toBe("/book?service=123");
    expect(safeReturnPath("https://attacker.example/path")).toBe("/account");
    expect(safeReturnPath("//attacker.example/path")).toBe("/account");
  });

  it("constructs the magic-link callback on the trusted site origin", () => {
    expect(getAuthConfirmUrl("https://attacker.example/path")).toBe(
      "http://localhost:3000/auth/confirm?returnTo=%2Faccount",
    );
  });
});

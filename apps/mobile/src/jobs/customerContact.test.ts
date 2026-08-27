import { describe, expect, it } from "vitest";
import { customerEmailUrl } from "./customerContact";

describe("staff job customer email", () => {
  it("creates the expected mailto action for the booking email", () => {
    expect(customerEmailUrl(" guest@example.com ")).toBe(
      "mailto:guest@example.com",
    );
  });
});

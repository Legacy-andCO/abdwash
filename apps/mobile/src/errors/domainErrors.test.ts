import { describe, expect, it } from "vitest";
import { ApiError, domainErrorMessage } from "./domainErrors";

describe("mobile API error presentation", () => {
  it("keeps request diagnostics off the customer-facing message", () => {
    const error = new ApiError(
      "REQUEST_FAILED",
      500,
      "REQUEST_FAILED",
      "2d0a0f98-ef17-4ca4-a01e-e7bd2e5a9231",
      "/api/v1/staff/teams",
    );
    expect(
      domainErrorMessage(error, "Team creation failed. Please try again."),
    ).toBe("Team creation failed. Please try again.");
  });

  it("still presents known domain errors with actionable copy", () => {
    expect(
      domainErrorMessage(
        new ApiError("SHIFT_ASSIGNMENT_CONFLICT", 409),
        "Please try again.",
      ),
    ).toContain("already has a shift");
  });
});

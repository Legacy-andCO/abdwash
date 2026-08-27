import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { isVehicleType, VEHICLE_TYPES } from "./vehicle-types";

describe("shared vehicle types", () => {
  it("is the single option source used by booking and profile editors", () => {
    const booking = readFileSync(
      new URL("../components/booking-wizard.tsx", import.meta.url),
      "utf8",
    );
    const profile = readFileSync(
      new URL("../components/customer-profile-manager.tsx", import.meta.url),
      "utf8",
    );
    expect(booking).toContain("VEHICLE_TYPES.map");
    expect(profile).toContain("VEHICLE_TYPES.map");
    expect(profile).toContain("<select");
  });

  it("rejects historical values while preserving all booking options", () => {
    expect(VEHICLE_TYPES).toEqual([
      "sedan",
      "suv",
      "hatchback",
      "coupe",
      "pickup",
      "van",
      "other",
    ]);
    expect(isVehicleType("suv")).toBe(true);
    expect(isVehicleType("legacy-limousine")).toBe(false);
  });
});

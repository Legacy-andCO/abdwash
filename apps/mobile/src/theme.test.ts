import { describe, expect, it } from "vitest";
import { brandColors } from "./brand-colors";

describe("Trifecta mobile theme", () => {
  it("shares the Trifecta semantic palette", () => {
    expect(brandColors.brandDark).toBe("#241C1A");
    expect(brandColors.primary).toBe("#D65A1F");
    expect(brandColors.primaryPressed).toBe("#B8461A");
    expect(brandColors.accent).toBe("#E8944A");
    expect(brandColors.background).toBe("#F4EDE4");
  });
});

import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

describe("homepage polish contract", () => {
  it("keeps benefit text on the readable dark brand token", () => {
    const css = source("../app/globals.css");
    expect(css).toMatch(/\.trust-row\s*\{\s*color: var\(--brand-dark\)/);
    expect(css).not.toMatch(/\.trust-row,\s*\.promo-copy[^}]+color: #e6dcd4/s);
  });

  it("contains matching English and Arabic loyalty content", () => {
    const translations = source("./i18n.ts");
    expect(translations).toContain('"home.loyaltyEyebrow": "Trifecta rewards"');
    expect(translations).toContain('"home.loyaltyEyebrow": "مكافآت ترايفكتا"');
  });
});

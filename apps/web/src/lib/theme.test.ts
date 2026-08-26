import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("Trifecta web theme", () => {
  it("defines the shared brand tokens and uses the authentic logo asset", () => {
    const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
    const mark = readFileSync(new URL("../components/brand-mark.tsx", import.meta.url), "utf8");
    expect(css).toContain("--brand-dark: #241c1a");
    expect(css).toContain("--brand-primary: #d65a1f");
    expect(css).toContain("--brand-background: #f4ede4");
    expect(mark).toContain("/brand/trifecta-logo.png");
  });
});


import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
const homepage = readFileSync(new URL("../app/page.tsx", import.meta.url), "utf8");
const layout = readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8");

describe("customer account and review UI contracts", () => {
  it("keeps the compact check-email state within small phone layouts", () => {
    expect(css).toContain(".auth-card .auth-magic-sent .confirmation-burst");
    expect(css).toContain("@media (max-width: 360px)");
    expect(css).toContain("padding-inline: 1.15rem");
  });

  it("uses real review components rather than hard-coded testimonials", () => {
    expect(homepage).toContain("<HomeReviews />");
    expect(homepage).not.toMatch(/4\.9|126 reviews|customer testimonial/i);
    expect(layout).toContain("<ReviewPrompt />");
  });

  it("has responsive review cards and RTL-safe logical positioning", () => {
    expect(css).toContain(".review-card-grid");
    expect(css).toContain("grid-template-columns: 1fr");
    expect(css).toContain("inset-inline-end: 1rem");
  });
});

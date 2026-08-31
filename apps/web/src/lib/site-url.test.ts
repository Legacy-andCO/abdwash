import { afterEach, describe, expect, it } from "vitest";
import { getPublicSiteUrl } from "./site-url";

const originalSiteUrl = process.env.NEXT_PUBLIC_SITE_URL;

afterEach(() => {
  if (originalSiteUrl === undefined) delete process.env.NEXT_PUBLIC_SITE_URL;
  else process.env.NEXT_PUBLIC_SITE_URL = originalSiteUrl;
});

describe("public site URL", () => {
  it("uses the canonical Trifecta production origin for trusted auth redirects", () => {
    process.env.NEXT_PUBLIC_SITE_URL = "https://trifecta-wash.com/";
    expect(getPublicSiteUrl()).toBe("https://trifecta-wash.com");
  });

  it("rejects an insecure non-local configured origin", () => {
    process.env.NEXT_PUBLIC_SITE_URL = "http://trifecta-wash.com";
    expect(getPublicSiteUrl()).toBe("http://localhost:3000");
  });
});

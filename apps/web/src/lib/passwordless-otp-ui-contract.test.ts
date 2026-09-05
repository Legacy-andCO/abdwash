import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

describe("passwordless cross-device OTP", () => {
  it("keeps the existing magic link and verifies email OTP through Supabase", () => {
    const auth = source("../components/auth-provider.tsx");
    const login = source("../components/login-form.tsx");
    expect(auth).toContain("client.auth.signInWithOtp");
    expect(auth).toContain("client.auth.verifyOtp");
    expect(auth).toContain('type: \"email\"');
    expect(login).toContain('autoComplete=\"one-time-code\"');
    expect(login).toContain('maxLength={6}');
    expect(login).toContain("replace(/\\D/g, \"\")");
  });

  it("includes both English and Arabic OTP copy", () => {
    const i18n = source("i18n.ts");
    expect(i18n).toContain("Accessing your email from another device?");
    expect(i18n).toContain("If you're accessing your email from a different device");
    expect(i18n).toContain("هل فتحت البريد الإلكتروني على جهاز آخر؟");
  });
});

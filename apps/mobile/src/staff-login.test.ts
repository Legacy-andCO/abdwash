import { describe, expect, it } from "vitest";
import { normalizeStaffUsername, staffLoginEmail } from "./staff-login";

describe("staff login identity", () => {
  it("normalizes usernames", () => {
    expect(normalizeStaffUsername("  Manager ")).toBe("manager");
  });
  it("converts usernames to internal staff emails", () => {
    expect(staffLoginEmail("employee")).toBe("employee@staff.abdwash.local");
  });
  it("preserves temporary email staff login compatibility", () => {
    expect(staffLoginEmail(" Existing.Staff@Example.com ")).toBe("existing.staff@example.com");
  });
});

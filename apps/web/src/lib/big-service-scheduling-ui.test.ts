import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

describe("big-service scheduling UI", () => {
  const wizard = source("../components/booking-wizard.tsx");
  const i18n = source("i18n.ts");

  it("renders the backend-provided special-start message near availability", () => {
    expect(wizard).toContain("state.availability?.required_start_time");
    expect(wizard).toContain("state.availability.slots.map");
    expect(wizard).toContain('t("booking.schedule.allDayNine")');
    expect(wizard).not.toContain('service.name === "Interior Deep Cleaning"');
    expect(wizard).not.toContain('service.name === "Exterior Polishing"');
  });

  it("includes English and Arabic customer copy", () => {
    expect(i18n).toContain(
      '"This service requires the day to complete, so appointments begin at 9:00 AM."',
    );
    expect(i18n).toContain(
      '"تتطلب هذه الخدمة يوماً كاملاً، لذلك تبدأ المواعيد الساعة 9:00 صباحاً."',
    );
  });
});

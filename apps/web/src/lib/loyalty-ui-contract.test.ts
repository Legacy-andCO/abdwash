import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

describe("customer loyalty UI contract", () => {
  it("shows authoritative progress, history, and available rewards", () => {
    const profile = source("../components/customer-profile-manager.tsx");
    expect(profile).toContain("data.loyalty.progress_washes");
    expect(profile).toContain("data.loyalty.available_rewards");
    expect(profile).toContain("data.loyalty.history.slice(0, 10)");
  });

  it("keeps reward selection attached to one booking vehicle", () => {
    const wizard = source("../components/booking-wizard.tsx");
    expect(wizard).toContain('type: "loyalty_reward"');
    expect(wizard).toContain("item.loyalty_reward_id === reward.id");
    expect(wizard).toContain("booking.review.loyaltyReward");
  });

  it("contains customer-facing English and Arabic loyalty translations", () => {
    const translations = source("./i18n.ts");
    expect(translations).toContain(
      '"profile.loyaltyTitle": "Your wash rewards"',
    );
    expect(translations).toContain(
      '"profile.loyaltyTitle": "مكافآت غسيل مركبتك"',
    );
    expect(translations).toContain('"booking.vehicles.rewardApply"');
  });
});

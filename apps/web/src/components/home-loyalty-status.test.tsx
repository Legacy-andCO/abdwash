// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HomeLoyaltyStatus } from "./home-loyalty-status";

const auth = vi.hoisted(() => ({
  user: null as { id: string } | null,
  loading: false,
}));
const loadCustomerProfile = vi.hoisted(() => vi.fn());

vi.mock("./auth-provider", () => ({ useAuth: () => auth }));
vi.mock("./i18n-provider", () => ({
  useI18n: () => ({
    language: "en",
    t: (key: string, values?: Record<string, string | number>) => {
      const messages: Record<string, string> = {
        "home.loyaltyEyebrow": "Trifecta rewards",
        "home.loyaltyProgress": `${values?.current} / ${values?.required} washes`,
        "home.loyaltyRemaining": `${values?.count} more washes until your free ${values?.service}.`,
        "home.loyaltyAvailable": `Free ${values?.service} available`,
        "home.loyaltyAvailableCopy": "Your reward is ready.",
        "home.loyaltyWash": "Standard Wash",
        "home.viewRewards": "View rewards",
        "home.bookReward": "Book reward",
      };
      return messages[key] ?? key;
    },
  }),
}));
vi.mock("@/lib/customer-profile-resource", () => ({
  cachedCustomerProfile: () => null,
  loadCustomerProfile,
}));

const bootstrap = (availableRewards: number) => ({
  authenticated_email: "customer@example.com",
  profile: null,
  addresses: [],
  vehicles: [],
  loyalty: {
    enabled: true,
    configured: true,
    required_washes: 9,
    progress_washes: 6,
    washes_remaining: 3,
    lifetime_qualifying_washes: 6,
    available_rewards: availableRewards,
    reserved_rewards: 0,
    redeemed_rewards: 0,
    reward_service: { id: "standard", name: "Standard Wash" },
    rewards: [],
    history: [],
  },
});

afterEach(() => {
  cleanup();
  auth.user = null;
  auth.loading = false;
  loadCustomerProfile.mockReset();
});

describe("homepage loyalty status", () => {
  it("does not request or expose private loyalty data to guests", () => {
    render(<HomeLoyaltyStatus />);
    expect(loadCustomerProfile).not.toHaveBeenCalled();
    expect(screen.queryByText("Trifecta rewards")).toBeNull();
  });

  it("renders authoritative progress without blocking the homepage", async () => {
    auth.user = { id: "customer-1" };
    let resolve!: (value: ReturnType<typeof bootstrap>) => void;
    loadCustomerProfile.mockReturnValue(
      new Promise((next) => {
        resolve = next;
      }),
    );
    const { container } = render(<HomeLoyaltyStatus />);
    expect(container.innerHTML).toBe("");
    resolve(bootstrap(0));
    expect(await screen.findByText("6 / 9 washes")).toBeTruthy();
    expect(screen.getByText("3 more washes until your free Standard Wash.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "View rewards" }).getAttribute("href")).toBe(
      "/account/profile#rewards",
    );
  });

  it("routes an available reward through the normal booking flow", async () => {
    auth.user = { id: "customer-1" };
    loadCustomerProfile.mockResolvedValue(bootstrap(1));
    render(<HomeLoyaltyStatus />);
    await waitFor(() => expect(screen.getByText("Free Standard Wash available")).toBeTruthy());
    expect(screen.getByRole("link", { name: "Book reward" }).getAttribute("href")).toBe(
      "/book?service=standard",
    );
  });
});

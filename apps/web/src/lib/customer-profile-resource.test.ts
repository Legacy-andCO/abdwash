import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CustomerProfileBootstrap } from "./types";

const getCustomerProfile = vi.hoisted(() => vi.fn());
vi.mock("./api", () => ({ getCustomerProfile }));

import {
  loadCustomerProfile,
  resetCustomerProfileResourceForTests,
} from "./customer-profile-resource";

const data: CustomerProfileBootstrap = {
  authenticated_email: "customer@example.com",
  profile: null,
  addresses: [],
  vehicles: [],
  loyalty: null,
};

beforeEach(() => {
  resetCustomerProfileResourceForTests();
  getCustomerProfile.mockReset();
});

describe("customer profile resource", () => {
  it("deduplicates the homepage/account request under one customer cache key", async () => {
    getCustomerProfile.mockResolvedValue(data);
    const first = loadCustomerProfile("customer-1");
    const second = loadCustomerProfile("customer-1");
    await expect(Promise.all([first, second])).resolves.toEqual([data, data]);
    expect(getCustomerProfile).toHaveBeenCalledOnce();
  });
});

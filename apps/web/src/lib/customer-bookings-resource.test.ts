import { beforeEach, describe, expect, it, vi } from "vitest";

const getCustomerBookings = vi.hoisted(() => vi.fn());
vi.mock("./api", () => ({ getCustomerBookings }));

import {
  loadCustomerBookings,
  resetCustomerBookingsResourceForTests,
} from "./customer-bookings-resource";

beforeEach(() => {
  resetCustomerBookingsResourceForTests();
  getCustomerBookings.mockReset();
});

describe("customer bookings resource", () => {
  it("single-flights homepage and account consumers per customer", async () => {
    getCustomerBookings.mockResolvedValue([]);
    const home = loadCustomerBookings("customer-1");
    const account = loadCustomerBookings("customer-1");
    await expect(Promise.all([home, account])).resolves.toEqual([[], []]);
    expect(getCustomerBookings).toHaveBeenCalledOnce();
  });

  it("serves fresh data without another request and supports explicit refresh", async () => {
    getCustomerBookings.mockResolvedValue([]);
    await loadCustomerBookings("customer-1");
    await loadCustomerBookings("customer-1");
    expect(getCustomerBookings).toHaveBeenCalledOnce();
    await loadCustomerBookings("customer-1", { refresh: true });
    expect(getCustomerBookings).toHaveBeenCalledTimes(2);
  });
});

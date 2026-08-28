// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "@/components/auth-provider";
import { getCustomerBookings } from "./api";
import { resetCustomerBookingsResourceForTests } from "./customer-bookings-resource";
import { useCustomerBookings } from "./use-customer-bookings";

vi.mock("@/components/auth-provider", () => ({ useAuth: vi.fn() }));
vi.mock("./api", () => ({ getCustomerBookings: vi.fn() }));

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
  resetCustomerBookingsResourceForTests();
});

describe("useCustomerBookings", () => {
  it("does not request private bookings for a guest", () => {
    vi.mocked(useAuth).mockReturnValue({ user: null, loading: false } as ReturnType<typeof useAuth>);
    const { result } = renderHook(() => useCustomerBookings());
    expect(result.current.bookings).toEqual([]);
    expect(getCustomerBookings).not.toHaveBeenCalled();
  });

  it("loads for a signed-in customer and only polls while the page is visible", async () => {
    vi.useFakeTimers();
    vi.mocked(useAuth).mockReturnValue({ user: { id: "customer" }, loading: false } as ReturnType<typeof useAuth>);
    vi.mocked(getCustomerBookings).mockResolvedValue([]);
    renderHook(() => useCustomerBookings({ polling: true }));
    await act(async () => { await Promise.resolve(); });
    expect(getCustomerBookings).toHaveBeenCalledTimes(1);
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
    await act(async () => { await vi.advanceTimersByTimeAsync(25_000); });
    expect(getCustomerBookings).toHaveBeenCalledTimes(1);
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
    await act(async () => { await vi.advanceTimersByTimeAsync(25_000); });
    expect(getCustomerBookings).toHaveBeenCalledTimes(2);
  });

  it("clears loading when the initial booking request fails", async () => {
    vi.mocked(useAuth).mockReturnValue({ user: { id: "customer" }, loading: false } as ReturnType<typeof useAuth>);
    vi.mocked(getCustomerBookings).mockRejectedValue(new Error("production failure"));
    const { result } = renderHook(() => useCustomerBookings());
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(result.current.error).toBe("We couldn’t load your bookings. Please try again.");
    expect(result.current.loading).toBe(false);
  });
});

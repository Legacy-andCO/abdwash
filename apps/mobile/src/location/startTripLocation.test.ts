import { afterEach, describe, expect, it, vi } from "vitest";
import { acquireTripOrigin, type TripLocationSource } from "./startTripLocation";

function source(overrides: Partial<TripLocationSource> = {}): TripLocationSource {
  return {
    getPermission: vi.fn(async () => ({ granted: true })),
    requestPermission: vi.fn(async () => ({ granted: true })),
    getLastKnown: vi.fn(async () => null),
    getCurrent: vi.fn(async () => ({
      timestamp: Date.now(),
      coords: { latitude: 24.45, longitude: 54.37, accuracy: 20 },
    })),
    ...overrides,
  };
}

afterEach(() => vi.useRealTimers());

describe("Start Trip location acquisition", () => {
  it("uses a recent accurate last-known location without waiting for GPS", async () => {
    const current = vi.fn();
    const adapter = source({
      getLastKnown: vi.fn(async () => ({
        timestamp: 999_000,
        coords: { latitude: 24.5, longitude: 54.4, accuracy: 30 },
      })),
      getCurrent: current,
    });
    await expect(acquireTripOrigin(adapter, 9_000, 1_000_000)).resolves.toEqual({
      origin: { latitude: 24.5, longitude: 54.4 },
      source: "last_known",
    });
    expect(current).not.toHaveBeenCalled();
  });

  it("times out current GPS acquisition after a bounded wait", async () => {
    vi.useFakeTimers();
    const pending = new Promise<never>(() => undefined);
    const result = acquireTripOrigin(source({ getCurrent: () => pending }), 9_000);
    await vi.advanceTimersByTimeAsync(9_000);
    await expect(result).resolves.toEqual({ origin: null, failure: "LOCATION_TIMEOUT" });
  });

  it("returns a permission failure that can drive the no-ETA confirmation", async () => {
    const adapter = source({
      getPermission: vi.fn(async () => ({ granted: false, canAskAgain: false })),
    });
    await expect(acquireTripOrigin(adapter)).resolves.toEqual({
      origin: null,
      failure: "LOCATION_PERMISSION_DENIED",
    });
    expect(adapter.getCurrent).not.toHaveBeenCalled();
  });
});

import { describe, expect, it, vi } from "vitest";
import type { TripLocationSource } from "./startTripLocation";
import { runStartTripFlow } from "./startTripFlow";

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

describe("Start Trip button flow", () => {
  it("runs button → location → API with a valid origin", async () => {
    const submit = vi.fn(async () => ({ status: "en_route" }));
    const phases: string[] = [];
    const onStage = vi.fn();
    await expect(runStartTripFlow({
      source: source(),
      submit,
      confirmFallback: vi.fn(async () => false),
      onStage,
      report: (phase) => phases.push(phase),
    })).resolves.toEqual({ status: "en_route" });
    expect(submit).toHaveBeenCalledWith({ latitude: 24.45, longitude: 54.37 });
    expect(onStage.mock.calls).toEqual([
      ["getting_location"],
      ["starting_trip"],
      ["idle"],
    ]);
    expect(phases).toEqual(expect.arrayContaining([
      "trip_button_pressed",
      "trip_location_current_started",
      "trip_location_success",
      "trip_api_started",
      "trip_api_success",
    ]));
  });

  it("runs the confirmed no-ETA fallback with origin null", async () => {
    const submit = vi.fn(async () => ({ status: "en_route" }));
    const phases: string[] = [];
    await runStartTripFlow({
      source: source({
        getPermission: vi.fn(async () => ({ granted: false, canAskAgain: false })),
      }),
      submit,
      confirmFallback: vi.fn(async () => true),
      onStage: vi.fn(),
      report: (phase) => phases.push(phase),
    });
    expect(submit).toHaveBeenCalledWith(null);
    expect(phases).toContain("trip_fallback_selected");
    expect(phases).toContain("trip_api_started");
  });
});

// @vitest-environment jsdom

import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { loadGoogleMaps } from "@/lib/google-maps-loader";
import type { Location } from "@/lib/types";

vi.mock("@/lib/google-maps-loader", () => ({ loadGoogleMaps: vi.fn() }));

const mapInstances: Array<{ center: unknown; panTo: ReturnType<typeof vi.fn>; setZoom: ReturnType<typeof vi.fn> }> = [];
const markerInstances: Array<{ map: unknown; position: unknown }> = [];
let LocationPicker: typeof import("./location-picker").LocationPicker;

class FakeAutocomplete extends HTMLElement {
  placeholder = "";
  description = "";
}

function installGoogle(importFailure = false, delays: Partial<Record<"maps" | "marker" | "places", number>> = {}) {
  const mapsGlobal = {
    maps: {
      importLibrary: vi.fn(async (name: string) => {
        if (importFailure) throw new Error("library failure");
        const delay = delays[name as keyof typeof delays];
        if (delay) await new Promise((resolve) => window.setTimeout(resolve, delay));
        if (name === "maps") return { Map: class {
          center: unknown;
          panTo = vi.fn();
          setZoom = vi.fn();
          constructor(_node: HTMLElement, options: { center: unknown }) { this.center = options.center; mapInstances.push(this); }
        } };
        if (name === "marker") return { AdvancedMarkerElement: class {
          map: unknown;
          position: unknown;
          constructor(options: { map: unknown; position: unknown }) { this.map = options.map; this.position = options.position; markerInstances.push(this); }
          addListener() { return { remove: vi.fn() }; }
        } };
        return { PlaceAutocompleteElement: FakeAutocomplete };
      }),
      Geocoder: class { geocode = vi.fn().mockResolvedValue({ results: [] }); },
    },
  } as unknown as typeof google;
  Object.defineProperty(window, "google", { configurable: true, value: mapsGlobal });
  vi.mocked(loadGoogleMaps).mockResolvedValue(mapsGlobal);
}

const baseLocation: Location = {
  written_address: "Al Reem Island, Abu Dhabi",
  location_url: "",
  latitude: null,
  longitude: null,
  instructions: "",
};

function renderPicker(location = baseLocation) {
  return render(<LocationPicker location={location} errors={{}} onFieldChange={vi.fn()} onCoordinatesChange={vi.fn()} />);
}

beforeAll(async () => {
  process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY = "public-test-key";
  if (!customElements.get("fake-place-autocomplete")) customElements.define("fake-place-autocomplete", FakeAutocomplete);
  LocationPicker = (await import("./location-picker")).LocationPicker;
});

afterEach(() => {
  cleanup();
  mapInstances.length = 0;
  markerInstances.length = 0;
  vi.clearAllMocks();
});

afterAll(() => { delete process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY; });

describe("LocationPicker Maps lifecycle", () => {
  it("shows the fallback without erasing the written location when initialization fails", async () => {
    vi.mocked(loadGoogleMaps).mockRejectedValue(new Error("load failed"));
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    renderPicker();
    expect(await screen.findByText("Map temporarily unavailable.")).toBeTruthy();
    expect(screen.getByDisplayValue("Al Reem Island, Abu Dhabi")).toBeTruthy();
    expect(screen.queryByLabelText("Selected service location map")).toBeNull();
    expect(consoleError).toHaveBeenCalledWith("[AbdWash Maps] loader_failed");
    consoleError.mockRestore();
  });

  it("becomes ready and creates one autocomplete widget", async () => {
    installGoogle();
    const view = renderPicker();
    await waitFor(() => expect(view.container.querySelectorAll("fake-place-autocomplete")).toHaveLength(1));
    expect(screen.getByLabelText("Selected service location map")).toBeTruthy();
    expect(mapInstances).toHaveLength(1);
    expect(markerInstances).toHaveLength(1);
  });

  it("stays loading until differently delayed valid libraries all resolve, then becomes ready", async () => {
    installGoogle(false, { maps: 10, marker: 20, places: 30 });
    const view = renderPicker();
    expect(screen.getByText("Loading map…")).toBeTruthy();
    expect(screen.queryByText("Map temporarily unavailable.")).toBeNull();
    await waitFor(() => expect(view.container.querySelectorAll("fake-place-autocomplete")).toHaveLength(1));
    expect(screen.queryByText("Loading map…")).toBeNull();
    expect(screen.queryByText("Map temporarily unavailable.")).toBeNull();
  });

  it("uses current saved coordinates as soon as Maps becomes ready", async () => {
    installGoogle();
    renderPicker({ ...baseLocation, latitude: 24.4539, longitude: 54.3773 });
    await waitFor(() => expect(markerInstances).toHaveLength(1));
    expect(markerInstances[0].position).toEqual({ lat: 24.4539, lng: 54.3773 });
    expect(markerInstances[0].map).toBeTruthy();
  });

  it("cleans component widgets and initializes once again after a remount", async () => {
    installGoogle();
    const first = renderPicker();
    await waitFor(() => expect(first.container.querySelectorAll("fake-place-autocomplete")).toHaveLength(1));
    first.unmount();
    expect(first.container.querySelectorAll("fake-place-autocomplete")).toHaveLength(0);
    const second = renderPicker();
    await waitFor(() => expect(second.container.querySelectorAll("fake-place-autocomplete")).toHaveLength(1));
    expect(mapInstances).toHaveLength(2);
  });

  it("turns an importLibrary rejection into the visible fallback", async () => {
    installGoogle(true);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    renderPicker();
    expect(await screen.findByText("Map temporarily unavailable.")).toBeTruthy();
    expect(consoleError).toHaveBeenCalledWith("[AbdWash Maps] maps_library_failed");
    expect(consoleError).toHaveBeenCalledWith("[AbdWash Maps] marker_library_failed");
    expect(consoleError).toHaveBeenCalledWith("[AbdWash Maps] places_library_failed");
    consoleError.mockRestore();
  });
});

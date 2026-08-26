// @vitest-environment jsdom

import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { loadGoogleMaps } from "@/lib/google-maps-loader";
import type { Location } from "@/lib/types";

vi.mock("@/lib/google-maps-loader", () => ({ loadGoogleMaps: vi.fn() }));

const mapInstances: Array<{ center: unknown; panTo: ReturnType<typeof vi.fn>; setZoom: ReturnType<typeof vi.fn>; listeners: Record<string, (event: unknown) => void> }> = [];
const markerInstances: Array<{ map: unknown; position: unknown }> = [];
let LocationPicker: typeof import("./location-picker").LocationPicker;

const place = {
  formattedAddress: "Yas Acres, Abu Dhabi",
  location: { lat: () => 24.47, lng: () => 54.36 },
  fetchFields: vi.fn(async () => undefined),
};
const prediction = {
  placeId: "yas-acres",
  text: { text: "Yas Acres, Abu Dhabi" },
  mainText: { text: "Yas Acres" },
  secondaryText: { text: "Abu Dhabi" },
  toPlace: () => place,
};
const fetchAutocompleteSuggestions = vi.fn(async () => ({ suggestions: [{ placePrediction: prediction }] }));

function installGoogle(importFailure = false, delays: Partial<Record<"maps" | "marker" | "places", number>> = {}) {
  const mapsGlobal = {
    maps: {
      event: { clearInstanceListeners: vi.fn() },
      importLibrary: vi.fn(async (name: string) => {
        if (importFailure) throw new Error("library failure");
        const delay = delays[name as keyof typeof delays];
        if (delay) await new Promise((resolve) => window.setTimeout(resolve, delay));
        if (name === "maps") return { Map: class {
          center: unknown;
          panTo = vi.fn();
          setZoom = vi.fn();
          listeners: Record<string, (event: unknown) => void> = {};
          constructor(node: HTMLElement, options: { center: unknown }) { this.center = options.center; node.append(document.createElement("div")); mapInstances.push(this); }
          addListener(name: string, callback: (event: unknown) => void) { this.listeners[name] = callback; return { remove: vi.fn() }; }
        } };
        if (name === "marker") return { AdvancedMarkerElement: class {
          map: unknown;
          position: unknown;
          constructor(options: { map: unknown; position: unknown }) { this.map = options.map; this.position = options.position; markerInstances.push(this); }
          addListener() { return { remove: vi.fn() }; }
        } };
        return {
          AutocompleteSessionToken: class {},
          AutocompleteSuggestion: { fetchAutocompleteSuggestions },
        };
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

function renderPicker(location = baseLocation, onCoordinatesChange = vi.fn()) {
  return render(<LocationPicker location={location} errors={{}} onFieldChange={vi.fn()} onCoordinatesChange={onCoordinatesChange} />);
}

beforeAll(async () => {
  process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY = "public-test-key";
  LocationPicker = (await import("./location-picker")).LocationPicker;
});

afterEach(() => {
  cleanup();
  mapInstances.length = 0;
  markerInstances.length = 0;
  fetchAutocompleteSuggestions.mockClear();
  place.fetchFields.mockClear();
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
    expect(consoleError).toHaveBeenCalledWith("[Trifecta Maps] loader_failed");
    consoleError.mockRestore();
  });

  it("becomes ready with a real editable search input", async () => {
    installGoogle();
    renderPicker();
    expect(await screen.findByLabelText("Search for an address or place")).toBeTruthy();
    expect(screen.getByLabelText("Selected service location map")).toBeTruthy();
    expect(mapInstances).toHaveLength(1);
    expect(markerInstances).toHaveLength(1);
  });

  it("stays loading until differently delayed valid libraries all resolve, then becomes ready", async () => {
    installGoogle(false, { maps: 10, marker: 20, places: 30 });
    renderPicker();
    expect(screen.getByText("Loading map…")).toBeTruthy();
    expect(screen.queryByText("Map temporarily unavailable.")).toBeNull();
    await waitFor(() => expect(screen.queryByText("Loading map…")).toBeNull());
    expect(screen.queryByText("Map temporarily unavailable.")).toBeNull();
  });

  it("uses current saved coordinates as soon as Maps becomes ready", async () => {
    installGoogle();
    renderPicker({ ...baseLocation, latitude: 24.4539, longitude: 54.3773 });
    await waitFor(() => expect(markerInstances).toHaveLength(1));
    expect(markerInstances[0].position).toEqual({ lat: 24.4539, lng: 54.3773 });
    expect(markerInstances[0].map).toBeTruthy();
  });

  it("selects coordinates when the customer taps the map", async () => {
    installGoogle();
    const onCoordinatesChange = vi.fn();
    renderPicker(baseLocation, onCoordinatesChange);
    await waitFor(() => expect(mapInstances).toHaveLength(1));
    mapInstances[0].listeners.click({ latLng: { lat: () => 24.47, lng: () => 54.36 } });
    await waitFor(() => expect(onCoordinatesChange).toHaveBeenCalledWith(
      { latitude: 24.47, longitude: 54.36 },
      undefined,
    ));
  });

  it("cleans component widgets and initializes once again after a remount", async () => {
    installGoogle();
    const first = renderPicker();
    await screen.findByLabelText("Search for an address or place");
    first.unmount();
    renderPicker();
    await screen.findByLabelText("Search for an address or place");
    expect(mapInstances).toHaveLength(2);
  });

  it("returns keyboard-accessible suggestions and selects a place", async () => {
    installGoogle();
    const onCoordinatesChange = vi.fn();
    renderPicker(baseLocation, onCoordinatesChange);
    const input = await screen.findByLabelText("Search for an address or place");
    fireEvent.change(input, { target: { value: "Yas" } });
    const optionRow = await screen.findByRole("option");
    expect(fetchAutocompleteSuggestions).toHaveBeenCalledWith(
      expect.objectContaining({
        input: "Yas",
        region: "ae",
        locationBias: {
          north: 26.4,
          south: 22.6,
          east: 56.5,
          west: 51.4,
        },
      }),
    );
    const option = optionRow.querySelector("button")!;
    option.focus();
    fireEvent.click(option);
    await waitFor(() => expect(onCoordinatesChange).toHaveBeenCalledWith(
      { latitude: 24.47, longitude: 54.36 },
      "Yas Acres, Abu Dhabi",
    ));
  });

  it("shows the manual fallback message and reports a provider failure", async () => {
    installGoogle();
    fetchAutocompleteSuggestions.mockRejectedValueOnce(
      new Error("INVALID_ARGUMENT"),
    );
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    renderPicker();
    const input = await screen.findByLabelText("Search for an address or place");
    fireEvent.change(input, { target: { value: "Khalidiyah" } });
    expect(await screen.findByText("We couldn’t load suggestions. You can still enter the address manually.")).toBeTruthy();
    expect(consoleError).toHaveBeenCalledWith(
      "[Trifecta Maps] autocomplete failed",
      expect.any(Error),
    );
    consoleError.mockRestore();
  });

  it("clears Google-owned map DOM before Strict Mode reinitializes", async () => {
    installGoogle();
    const view = render(<StrictMode><LocationPicker location={baseLocation} errors={{}} onFieldChange={vi.fn()} onCoordinatesChange={vi.fn()} /></StrictMode>);
    await screen.findByLabelText("Search for an address or place");
    expect(view.container.querySelectorAll(".map-canvas > div")).toHaveLength(1);
  });

  it("turns an importLibrary rejection into the visible fallback", async () => {
    installGoogle(true);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    renderPicker();
    expect(await screen.findByText("Map temporarily unavailable.")).toBeTruthy();
    expect(consoleError).toHaveBeenCalledWith("[Trifecta Maps] maps_library_failed");
    expect(consoleError).toHaveBeenCalledWith("[Trifecta Maps] marker_library_failed");
    expect(consoleError).toHaveBeenCalledWith("[Trifecta Maps] places_library_failed");
    consoleError.mockRestore();
  });
});

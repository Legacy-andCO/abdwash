import { describe, expect, it, vi } from "vitest";
import { bookingReducer, initialBookingState } from "./booking-state";
import {
  coordinatesAreValid,
  googleMapsUrl,
  isSupportedGoogleMapsUrl,
  locationWithCoordinates,
  requestCurrentCoordinates,
} from "./location";

describe("location handling", () => {
  it("accepts supported full and short Google Maps links", () => {
    expect(isSupportedGoogleMapsUrl("https://www.google.com/maps/place/Yas+Acres")).toBe(true);
    expect(isSupportedGoogleMapsUrl("https://maps.app.goo.gl/AbCd1234")).toBe(true);
  });

  it("rejects generic and lookalike HTTPS domains", () => {
    expect(isSupportedGoogleMapsUrl("https://example.com/maps/place/Yas")).toBe(false);
    expect(isSupportedGoogleMapsUrl("https://google.com.attacker.com/maps/Yas")).toBe(false);
  });

  it("validates coordinate bounds", () => {
    expect(coordinatesAreValid({ latitude: 24.5, longitude: 54.4 })).toBe(true);
    expect(coordinatesAreValid({ latitude: 91, longitude: 54.4 })).toBe(false);
    expect(coordinatesAreValid({ latitude: 24.5, longitude: -181 })).toBe(false);
  });

  it("generates an encoded official Maps URL", () => {
    expect(googleMapsUrl({ latitude: 24.4539, longitude: 54.3773 })).toBe(
      "https://www.google.com/maps/search/?api=1&query=24.4539%2C54.3773",
    );
  });

  it("updates location state from a selected place", () => {
    const result = bookingReducer(initialBookingState, {
      type: "location_coordinates",
      value: { latitude: 24.42, longitude: 54.61 },
      writtenAddress: "Yas Acres, Abu Dhabi",
    });
    expect(result.location).toMatchObject({ latitude: 24.42, longitude: 54.61, written_address: "Yas Acres, Abu Dhabi" });
  });

  it("updates a location value from GPS coordinates", () => {
    expect(locationWithCoordinates(initialBookingState.location, { latitude: 25.2, longitude: 55.3 })).toMatchObject({ latitude: 25.2, longitude: 55.3 });
  });

  it("uses mocked browser geolocation without requesting a real position", async () => {
    const getCurrentPosition = vi.fn((success: PositionCallback) => success({ coords: { latitude: 25.2, longitude: 55.3 } } as GeolocationPosition));
    const geolocation = { getCurrentPosition } as unknown as Geolocation;
    await expect(requestCurrentCoordinates(geolocation)).resolves.toEqual({ latitude: 25.2, longitude: 55.3 });
    expect(getCurrentPosition).toHaveBeenCalledTimes(1);
  });

  it("falls back cleanly when geolocation is unavailable", async () => {
    await expect(requestCurrentCoordinates(undefined)).rejects.toThrow("GEOLOCATION_UNSUPPORTED");
  });
});

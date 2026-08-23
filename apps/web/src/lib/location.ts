import type { Location } from "./types";

export type Coordinates = { latitude: number; longitude: number };

export function coordinatesAreValid(coordinates: Coordinates): boolean {
  return (
    Number.isFinite(coordinates.latitude) &&
    coordinates.latitude >= -90 &&
    coordinates.latitude <= 90 &&
    Number.isFinite(coordinates.longitude) &&
    coordinates.longitude >= -180 &&
    coordinates.longitude <= 180
  );
}

export function googleMapsUrl(coordinates: Coordinates): string {
  if (!coordinatesAreValid(coordinates)) throw new RangeError("Invalid map coordinates");
  const query = `${coordinates.latitude},${coordinates.longitude}`;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
}

export function isSupportedGoogleMapsUrl(value: string): boolean {
  try {
    const url = new URL(value);
    const hostname = url.hostname.toLowerCase().replace(/\.$/, "");
    if (url.protocol !== "https:" || url.username || url.password || url.port) return false;
    if (hostname === "maps.app.goo.gl") return url.pathname.replaceAll("/", "").length > 0;
    if (hostname === "maps.google.com") return true;
    return (
      (hostname === "google.com" || hostname === "www.google.com") &&
      (url.pathname === "/maps" || url.pathname.startsWith("/maps/"))
    );
  } catch {
    return false;
  }
}

export function locationWithCoordinates(
  location: Location,
  coordinates: Coordinates,
  writtenAddress?: string,
): Location {
  if (!coordinatesAreValid(coordinates)) throw new RangeError("Invalid map coordinates");
  return {
    ...location,
    written_address: writtenAddress || location.written_address,
    latitude: coordinates.latitude,
    longitude: coordinates.longitude,
    location_url: googleMapsUrl(coordinates),
  };
}

export function requestCurrentCoordinates(
  geolocation: Geolocation | undefined,
): Promise<Coordinates> {
  if (!geolocation) return Promise.reject(new Error("GEOLOCATION_UNSUPPORTED"));
  return new Promise((resolve, reject) => {
    geolocation.getCurrentPosition(
      ({ coords }) => resolve({ latitude: coords.latitude, longitude: coords.longitude }),
      () => reject(new Error("GEOLOCATION_UNAVAILABLE")),
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 },
    );
  });
}

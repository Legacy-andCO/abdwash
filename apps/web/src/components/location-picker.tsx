"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import {
  requestCurrentCoordinates,
  type Coordinates,
} from "@/lib/location";
import type { Location } from "@/lib/types";

const googleMapsApiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
const googleMapsMapId = process.env.NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID ?? "DEMO_MAP_ID";
const uaeCenter = { lat: 24.4539, lng: 54.3773 };

type LocationPickerProps = {
  location: Location;
  errors: Record<string, string>;
  onFieldChange: (field: "written_address" | "location_url" | "instructions", value: string) => void;
  onCoordinatesChange: (coordinates: Coordinates, writtenAddress?: string) => void;
};

type PlaceSelectEvent = Event & {
  placePrediction: google.maps.places.PlacePrediction;
};

export function LocationPicker({
  location,
  errors,
  onFieldChange,
  onCoordinatesChange,
}: LocationPickerProps) {
  const mapElement = useRef<HTMLDivElement>(null);
  const autocompleteHost = useRef<HTMLDivElement>(null);
  const initialLocation = useRef(location);
  const map = useRef<google.maps.Map | null>(null);
  const marker = useRef<google.maps.marker.AdvancedMarkerElement | null>(null);
  const geocoder = useRef<google.maps.Geocoder | null>(null);
  const [mapsReady, setMapsReady] = useState(false);
  const [mapsFailed, setMapsFailed] = useState(false);
  const [gpsState, setGpsState] = useState<"idle" | "loading" | "error">("idle");

  useEffect(() => {
    if (!mapsReady || !mapElement.current || !autocompleteHost.current || map.current) return;
    let active = true;
    const host = autocompleteHost.current;

    async function initialize() {
      const [mapsLibrary, markerLibrary, placesLibrary] = await Promise.all([
        google.maps.importLibrary("maps") as Promise<google.maps.MapsLibrary>,
        google.maps.importLibrary("marker") as Promise<google.maps.MarkerLibrary>,
        google.maps.importLibrary("places") as Promise<google.maps.PlacesLibrary>,
      ]);
      const { Map } = mapsLibrary;
      const { AdvancedMarkerElement } = markerLibrary;
      const { PlaceAutocompleteElement } = placesLibrary;
      if (!active || !mapElement.current) return;

      const initialPosition = initialLocation.current.latitude !== null && initialLocation.current.longitude !== null
        ? { lat: initialLocation.current.latitude, lng: initialLocation.current.longitude }
        : uaeCenter;
      map.current = new Map(mapElement.current, {
        center: initialPosition,
        zoom: initialLocation.current.latitude !== null ? 17 : 8,
        mapId: googleMapsMapId,
        gestureHandling: "cooperative",
        streetViewControl: false,
        mapTypeControl: false,
      });
      geocoder.current = new google.maps.Geocoder();

      marker.current = new AdvancedMarkerElement({
        map: initialLocation.current.latitude !== null ? map.current : null,
        position: initialPosition,
        title: "Service location",
        gmpDraggable: true,
      });
      marker.current.addListener("dragend", async () => {
        const position = marker.current?.position;
        if (!position) return;
        const latitude = typeof position.lat === "function" ? position.lat() : Number(position.lat);
        const longitude = typeof position.lng === "function" ? position.lng() : Number(position.lng);
        const address = await reverseGeocode({ latitude, longitude });
        onCoordinatesChange({ latitude, longitude }, address);
      });

      const autocomplete = new PlaceAutocompleteElement({
        locationBias: { center: uaeCenter, radius: 250_000 },
      });
      autocomplete.placeholder = "Search for an address or place…";
      autocomplete.description = "Search for the AbdWash service address or place";
      autocomplete.addEventListener("gmp-select", (async (event: PlaceSelectEvent) => {
        const place = event.placePrediction.toPlace();
        await place.fetchFields({ fields: ["formattedAddress", "location"] });
        if (!place.location) return;
        const coordinates = {
          latitude: place.location.lat(),
          longitude: place.location.lng(),
        };
        onCoordinatesChange(coordinates, place.formattedAddress ?? undefined);
      }) as unknown as EventListener);
      host.replaceChildren(autocomplete);
    }

    async function reverseGeocode(coordinates: Coordinates): Promise<string | undefined> {
      try {
        const response = await geocoder.current?.geocode({
          location: { lat: coordinates.latitude, lng: coordinates.longitude },
        });
        return response?.results[0]?.formatted_address;
      } catch {
        return undefined;
      }
    }

    void initialize();
    return () => {
      active = false;
      if (marker.current) marker.current.map = null;
      marker.current = null;
      map.current = null;
      host.replaceChildren();
    };
  }, [mapsReady, onCoordinatesChange]);

  useEffect(() => {
    if (
      !map.current ||
      !marker.current ||
      location.latitude === null ||
      location.longitude === null
    ) return;
    const position = { lat: location.latitude, lng: location.longitude };
    marker.current.map = map.current;
    marker.current.position = position;
    map.current.panTo(position);
    map.current.setZoom(17);
  }, [location.latitude, location.longitude]);

  async function handleCurrentLocation() {
    setGpsState("loading");
    try {
      const coordinates = await requestCurrentCoordinates(navigator.geolocation);
      let address: string | undefined;
      if (geocoder.current) {
        try {
          const response = await geocoder.current.geocode({
            location: { lat: coordinates.latitude, lng: coordinates.longitude },
          });
          address = response.results[0]?.formatted_address;
        } catch {
          address = undefined;
        }
      }
      onCoordinatesChange(coordinates, address);
      setGpsState("idle");
    } catch {
      setGpsState("error");
    }
  }

  const hasCoordinates = location.latitude !== null && location.longitude !== null;

  return (
    <div className="location-picker">
      {googleMapsApiKey && (
        <Script
          id="google-maps-platform"
          src={`https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(googleMapsApiKey)}&v=weekly&loading=async&libraries=places,marker`}
          strategy="afterInteractive"
          onReady={() => setMapsReady(true)}
          onError={() => setMapsFailed(true)}
        />
      )}

      <button
        className="button button-ghost location-button"
        type="button"
        disabled={gpsState === "loading"}
        onClick={() => void handleCurrentLocation()}
      >
        <span aria-hidden="true">⌖</span>
        {gpsState === "loading" ? "Finding your location…" : "Use my current location"}
      </button>
      <div className="location-status" aria-live="polite">
        {gpsState === "error" && "We couldn't access your location. You can search for the address or enter it manually instead."}
      </div>

      <div className="location-divider"><span>or</span></div>

      {googleMapsApiKey && !mapsFailed ? (
        <div className="places-search" role="group" aria-labelledby="places-label">
          <span id="places-label">Search for an address or place</span>
          <div ref={autocompleteHost} />
        </div>
      ) : (
        <div className="inline-notice">
          <strong>Map search is temporarily unavailable.</strong>
          <span>Enter the written address and share a Google Maps link below.</span>
        </div>
      )}

      {googleMapsApiKey && !mapsFailed && <div className={hasCoordinates ? "map-preview visible" : "map-preview"}>
        <div ref={mapElement} aria-label="Selected service location map" />
      </div>}
      {hasCoordinates && <p className="pin-hint">Drag the pin to the exact service location.</p>}
      {errors.location && <span className="field-error" role="alert">{errors.location}</span>}

      <label>
        <span>Address</span>
        <textarea
          rows={3}
          value={location.written_address}
          aria-invalid={!!errors.written_address}
          aria-describedby={errors.written_address ? "address-error" : undefined}
          onChange={(event) => onFieldChange("written_address", event.target.value)}
        />
        {errors.written_address && <span className="field-error" id="address-error" role="alert">{errors.written_address}</span>}
      </label>

      <label>
        <span>Location notes <em>Optional</em></span>
        <textarea
          rows={2}
          placeholder="Parking access, building entrance, or anything useful"
          value={location.instructions}
          onChange={(event) => onFieldChange("instructions", event.target.value)}
        />
      </label>

      <details className="manual-map-link">
        <summary>Have a Google Maps link instead?</summary>
        <label>
          <span>Paste Google Maps link</span>
          <input
            type="url"
            placeholder="https://maps.app.goo.gl/…"
            value={location.location_url}
            aria-invalid={!!errors.location_url}
            aria-describedby={errors.location_url ? "map-error" : "map-hint"}
            onChange={(event) => onFieldChange("location_url", event.target.value)}
          />
          <small id="map-hint" className="field-hint">Only supported Google Maps share links are accepted.</small>
          {errors.location_url && <span className="field-error" id="map-error" role="alert">{errors.location_url}</span>}
        </label>
      </details>
    </div>
  );
}

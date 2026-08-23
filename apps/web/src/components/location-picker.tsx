"use client";

import { useEffect, useRef, useState } from "react";
import { loadGoogleMaps } from "@/lib/google-maps-loader";
import { requestCurrentCoordinates, type Coordinates } from "@/lib/location";
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

type PlaceSelectEvent = Event & { placePrediction: google.maps.places.PlacePrediction };
type MapState = "idle" | "loading" | "ready" | "failed";
type GpsState = "idle" | "loading" | "success" | "error";
type MapsFailureStage = "loader_failed" | "maps_library_failed" | "marker_library_failed" | "places_library_failed" | "map_construction_failed" | "geocoder_construction_failed" | "marker_construction_failed" | "autocomplete_construction_failed";

function reportMapsFailure(stage: MapsFailureStage) {
  console.error(`[AbdWash Maps] ${stage}`);
}

export function LocationPicker({ location, errors, onFieldChange, onCoordinatesChange }: LocationPickerProps) {
  const mapElement = useRef<HTMLDivElement>(null);
  const autocompleteHost = useRef<HTMLDivElement>(null);
  const locationRef = useRef(location);
  const coordinatesCallbackRef = useRef(onCoordinatesChange);
  const map = useRef<google.maps.Map | null>(null);
  const marker = useRef<google.maps.marker.AdvancedMarkerElement | null>(null);
  const geocoder = useRef<google.maps.Geocoder | null>(null);
  const [mapState, setMapState] = useState<MapState>("idle");
  const [gpsState, setGpsState] = useState<GpsState>("idle");

  useEffect(() => { locationRef.current = location; }, [location]);
  useEffect(() => { coordinatesCallbackRef.current = onCoordinatesChange; }, [onCoordinatesChange]);

  useEffect(() => {
    let active = true;
    let autocomplete: google.maps.places.PlaceAutocompleteElement | null = null;
    let autocompleteListener: EventListener | null = null;
    let markerListener: google.maps.MapsEventListener | null = null;
    const host = autocompleteHost.current;
    const mapNode = mapElement.current;

    const cleanupComponentObjects = () => {
      markerListener?.remove();
      markerListener = null;
      if (marker.current) marker.current.map = null;
      marker.current = null;
      if (autocomplete && autocompleteListener) autocomplete.removeEventListener("gmp-select", autocompleteListener);
      autocomplete = null;
      host?.replaceChildren();
      geocoder.current = null;
      map.current = null;
    };

    async function reverseGeocode(coordinates: Coordinates): Promise<string | undefined> {
      try {
        const response = await geocoder.current?.geocode({ location: { lat: coordinates.latitude, lng: coordinates.longitude } });
        return response?.results[0]?.formatted_address;
      } catch {
        return undefined;
      }
    }

    async function initialize() {
      setMapState("loading");
      try {
        let mapsGlobal: typeof google;
        try {
          mapsGlobal = await loadGoogleMaps(googleMapsApiKey);
        } catch (error) {
          reportMapsFailure("loader_failed");
          throw error;
        }
        if (!active || !mapNode?.isConnected || !host?.isConnected) return;
        const importLibrary = async <T,>(name: string, failureStage: MapsFailureStage) => {
          try {
            return await mapsGlobal.maps.importLibrary(name) as T;
          } catch (error) {
            reportMapsFailure(failureStage);
            throw error;
          }
        };
        const [mapsLibrary, markerLibrary, placesLibrary] = await Promise.all([
          importLibrary<google.maps.MapsLibrary>("maps", "maps_library_failed"),
          importLibrary<google.maps.MarkerLibrary>("marker", "marker_library_failed"),
          importLibrary<google.maps.PlacesLibrary>("places", "places_library_failed"),
        ]);
        if (!active || !mapNode.isConnected || !host.isConnected) return;

        const currentLocation = locationRef.current;
        const hasCoordinates = currentLocation.latitude !== null && currentLocation.longitude !== null;
        const initialPosition = hasCoordinates
          ? { lat: currentLocation.latitude!, lng: currentLocation.longitude! }
          : uaeCenter;
        try {
          map.current = new mapsLibrary.Map(mapNode, {
            center: initialPosition,
            zoom: hasCoordinates ? 17 : 8,
            mapId: googleMapsMapId,
            gestureHandling: "cooperative",
            streetViewControl: false,
            mapTypeControl: false,
          });
        } catch (error) {
          reportMapsFailure("map_construction_failed");
          throw error;
        }
        try {
          geocoder.current = new mapsGlobal.maps.Geocoder();
        } catch (error) {
          reportMapsFailure("geocoder_construction_failed");
          throw error;
        }
        try {
          marker.current = new markerLibrary.AdvancedMarkerElement({
            map: hasCoordinates ? map.current : null,
            position: initialPosition,
            title: "Service location",
            gmpDraggable: true,
          });
        } catch (error) {
          reportMapsFailure("marker_construction_failed");
          throw error;
        }
        markerListener = marker.current.addListener("dragend", async () => {
          const position = marker.current?.position;
          if (!position) return;
          const latitude = typeof position.lat === "function" ? position.lat() : Number(position.lat);
          const longitude = typeof position.lng === "function" ? position.lng() : Number(position.lng);
          const address = await reverseGeocode({ latitude, longitude });
          if (active) coordinatesCallbackRef.current({ latitude, longitude }, address);
        });

        try {
          autocomplete = new placesLibrary.PlaceAutocompleteElement({ locationBias: { center: uaeCenter, radius: 250_000 } });
          autocomplete.placeholder = "Search for an address or place…";
          autocomplete.description = "Search for an Abu Dhabi service address or place";
          autocompleteListener = (async (event: PlaceSelectEvent) => {
            const place = event.placePrediction.toPlace();
            await place.fetchFields({ fields: ["formattedAddress", "location"] });
            if (!active || !place.location) return;
            coordinatesCallbackRef.current(
              { latitude: place.location.lat(), longitude: place.location.lng() },
              place.formattedAddress ?? undefined,
            );
          }) as unknown as EventListener;
          autocomplete.addEventListener("gmp-select", autocompleteListener);
          host.replaceChildren(autocomplete);
        } catch (error) {
          reportMapsFailure("autocomplete_construction_failed");
          throw error;
        }
        if (active) setMapState("ready");
      } catch {
        cleanupComponentObjects();
        if (!active) return;
        setMapState("failed");
      }
    }

    void initialize();
    return () => { active = false; cleanupComponentObjects(); };
  }, []);

  useEffect(() => {
    if (mapState !== "ready" || !map.current || !marker.current || location.latitude === null || location.longitude === null) return;
    const position = { lat: location.latitude, lng: location.longitude };
    marker.current.map = map.current;
    marker.current.position = position;
    map.current.panTo(position);
    map.current.setZoom(17);
  }, [location.latitude, location.longitude, mapState]);

  async function handleCurrentLocation() {
    setGpsState("loading");
    try {
      const coordinates = await requestCurrentCoordinates(navigator.geolocation);
      let address: string | undefined;
      if (geocoder.current) {
        try {
          const response = await geocoder.current.geocode({ location: { lat: coordinates.latitude, lng: coordinates.longitude } });
          address = response.results[0]?.formatted_address;
        } catch {
          address = undefined;
        }
      }
      coordinatesCallbackRef.current(coordinates, address);
      setGpsState("success");
    } catch {
      setGpsState("error");
    }
  }

  const hasCoordinates = location.latitude !== null && location.longitude !== null;
  const mapIsPending = mapState === "idle" || mapState === "loading";

  return <div className="location-picker">
    <button className="button button-ghost location-button" type="button" disabled={gpsState === "loading"} onClick={() => void handleCurrentLocation()}><span aria-hidden="true">⌖</span>{gpsState === "loading" ? "Finding your location…" : "Use my current location"}</button>
    <div className={gpsState === "error" ? "location-status error" : "location-status"} aria-live="polite">{gpsState === "success" && "Location coordinates found."}{gpsState === "error" && "We couldn't access your location. You can search for the address or enter it manually instead."}</div>
    <div className="location-divider"><span>or</span></div>

    {mapState !== "failed" ? <>
      <div className={mapState === "ready" ? "places-search" : "places-search pending"} role="group" aria-labelledby="places-label"><span id="places-label">Search for an address or place</span><div ref={autocompleteHost} /></div>
      <div className={hasCoordinates ? "map-preview visible" : "map-preview"} aria-busy={mapIsPending}><div ref={mapElement} className="map-canvas" aria-label="Selected service location map" />{mapIsPending && <div className="map-loading" role="status"><span className="spinner dark" /> Loading map…</div>}</div>
    </> : <div className="inline-notice map-fallback" role="status"><strong>Map temporarily unavailable.</strong><span>You can still enter your address or share a Google Maps link.</span></div>}

    {hasCoordinates && <p className="pin-hint">{mapState === "ready" ? "Drag the pin to the exact service location." : "Location coordinates are saved for this booking."}</p>}
    {errors.location && <span className="field-error" role="alert">{errors.location}</span>}
    <label><span>Address</span><textarea rows={3} value={location.written_address} aria-invalid={!!errors.written_address} aria-describedby={errors.written_address ? "address-error" : undefined} onChange={(event) => onFieldChange("written_address", event.target.value)} />{errors.written_address && <span className="field-error" id="address-error" role="alert">{errors.written_address}</span>}</label>
    <label><span>Location notes <em>Optional</em></span><textarea rows={2} placeholder="Parking access, building entrance, or anything useful" value={location.instructions} onChange={(event) => onFieldChange("instructions", event.target.value)} /></label>
    <details className="manual-map-link"><summary>Have a Google Maps link instead?</summary><label><span>Paste Google Maps link</span><input type="url" placeholder="https://maps.app.goo.gl/…" value={location.location_url} aria-invalid={!!errors.location_url} aria-describedby={errors.location_url ? "map-error" : "map-hint"} onChange={(event) => onFieldChange("location_url", event.target.value)} /><small id="map-hint" className="field-hint">Only supported Google Maps share links are accepted.</small>{errors.location_url && <span className="field-error" id="map-error" role="alert">{errors.location_url}</span>}</label></details>
  </div>;
}

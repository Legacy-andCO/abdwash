"use client";

import { useEffect, useRef, useState } from "react";
import { loadGoogleMaps } from "@/lib/google-maps-loader";
import { requestCurrentCoordinates, type Coordinates } from "@/lib/location";
import type { Location } from "@/lib/types";
import { useI18n } from "./i18n-provider";

const googleMapsApiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
const googleMapsMapId = process.env.NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID ?? "DEMO_MAP_ID";
const uaeCenter = { lat: 24.4539, lng: 54.3773 };

type LocationPickerProps = {
  location: Location;
  errors: Record<string, string>;
  onFieldChange: (field: "written_address" | "location_url" | "instructions", value: string) => void;
  onCoordinatesChange: (coordinates: Coordinates, writtenAddress?: string) => void;
};

type MapState = "idle" | "loading" | "ready" | "failed";
type GpsState = "idle" | "loading" | "success" | "error";
type SearchState = "idle" | "loading" | "failed";
type MapsFailureStage = "loader_failed" | "maps_library_failed" | "marker_library_failed" | "places_library_failed" | "map_construction_failed" | "geocoder_construction_failed" | "marker_construction_failed" | "autocomplete_construction_failed";

function reportMapsFailure(stage: MapsFailureStage) {
  console.error(`[Trifecta Maps] ${stage}`);
}

export function LocationPicker({ location, errors, onFieldChange, onCoordinatesChange }: LocationPickerProps) {
  const { t } = useI18n();
  const translationRef = useRef(t);
  const mapElement = useRef<HTMLDivElement>(null);
  const locationRef = useRef(location);
  const coordinatesCallbackRef = useRef(onCoordinatesChange);
  const map = useRef<google.maps.Map | null>(null);
  const marker = useRef<google.maps.marker.AdvancedMarkerElement | null>(null);
  const geocoder = useRef<google.maps.Geocoder | null>(null);
  const places = useRef<google.maps.PlacesLibrary | null>(null);
  const autocompleteSession = useRef<google.maps.places.AutocompleteSessionToken | null>(null);
  const searchRequest = useRef(0);
  const [mapState, setMapState] = useState<MapState>("idle");
  const [gpsState, setGpsState] = useState<GpsState>("idle");
  const [searchState, setSearchState] = useState<SearchState>("idle");
  const [searchText, setSearchText] = useState("");
  const [suggestions, setSuggestions] = useState<google.maps.places.PlacePrediction[]>([]);

  useEffect(() => { locationRef.current = location; }, [location]);
  useEffect(() => { coordinatesCallbackRef.current = onCoordinatesChange; }, [onCoordinatesChange]);
  useEffect(() => { translationRef.current = t; }, [t]);

  useEffect(() => {
    let active = true;
    let mapsGlobal: typeof google | null = null;
    let markerListener: google.maps.MapsEventListener | null = null;
    let mapClickListener: google.maps.MapsEventListener | null = null;
    const mapNode = mapElement.current;

    const cleanupComponentObjects = () => {
      markerListener?.remove();
      markerListener = null;
      mapClickListener?.remove();
      mapClickListener = null;
      if (marker.current) marker.current.map = null;
      marker.current = null;
      if (map.current && mapsGlobal) mapsGlobal.maps.event.clearInstanceListeners(map.current);
      geocoder.current = null;
      map.current = null;
      places.current = null;
      autocompleteSession.current = null;
      mapNode?.replaceChildren();
    };

    async function reverseGeocode(coordinates: Coordinates): Promise<string | undefined> {
      try {
        const response = await geocoder.current?.geocode({ location: { lat: coordinates.latitude, lng: coordinates.longitude } });
        return response?.results[0]?.formatted_address;
      } catch {
        return undefined;
      }
    }

    async function selectCoordinates(coordinates: Coordinates) {
      const address = await reverseGeocode(coordinates);
      if (active) coordinatesCallbackRef.current(coordinates, address);
    }

    async function initialize() {
      setMapState("loading");
      try {
        try {
          mapsGlobal = await loadGoogleMaps(googleMapsApiKey);
        } catch (error) {
          reportMapsFailure("loader_failed");
          throw error;
        }
        if (!active || !mapNode?.isConnected) return;
        const readyGoogle = mapsGlobal;
        const importLibrary = async <T,>(name: string, failureStage: MapsFailureStage) => {
          try {
            return await readyGoogle.maps.importLibrary(name) as T;
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
        if (!active || !mapNode.isConnected) return;

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
          geocoder.current = new readyGoogle.maps.Geocoder();
        } catch (error) {
          reportMapsFailure("geocoder_construction_failed");
          throw error;
        }
        try {
          marker.current = new markerLibrary.AdvancedMarkerElement({
            map: hasCoordinates ? map.current : null,
            position: initialPosition,
            title: translationRef.current("booking.details.serviceLocation"),
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
          await selectCoordinates({ latitude, longitude });
        });
        mapClickListener = map.current.addListener("click", (event: google.maps.MapMouseEvent) => {
          if (!event.latLng) return;
          void selectCoordinates({
            latitude: event.latLng.lat(),
            longitude: event.latLng.lng(),
          });
        });

        places.current = placesLibrary;
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
    const value = searchText.trim();
    if (mapState !== "ready" || !places.current || value.length < 2) {
      setSuggestions([]);
      setSearchState("idle");
      return;
    }
    const requestId = ++searchRequest.current;
    const timer = window.setTimeout(async () => {
      const library = places.current;
      if (!library) return;
      setSearchState("loading");
      try {
        autocompleteSession.current ??= new library.AutocompleteSessionToken();
        const response = await library.AutocompleteSuggestion.fetchAutocompleteSuggestions({
          input: value,
          locationBias: { center: uaeCenter, radius: 250_000 },
          region: "ae",
          sessionToken: autocompleteSession.current,
        });
        if (requestId !== searchRequest.current) return;
        setSuggestions(
          response.suggestions
            .map((suggestion) => suggestion.placePrediction)
            .filter((prediction): prediction is google.maps.places.PlacePrediction => prediction !== null),
        );
        setSearchState("idle");
      } catch {
        if (requestId !== searchRequest.current) return;
        setSuggestions([]);
        setSearchState("failed");
      }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [mapState, searchText]);

  async function selectPlace(prediction: google.maps.places.PlacePrediction) {
    setSearchState("loading");
    try {
      const place = prediction.toPlace();
      await place.fetchFields({ fields: ["formattedAddress", "location"] });
      if (!place.location) throw new Error("Place has no location");
      const address = place.formattedAddress ?? prediction.text.text;
      setSearchText(address);
      setSuggestions([]);
      autocompleteSession.current = null;
      coordinatesCallbackRef.current(
        { latitude: place.location.lat(), longitude: place.location.lng() },
        address,
      );
      setSearchState("idle");
    } catch {
      setSearchState("failed");
    }
  }

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
    <button className="button button-ghost location-button" type="button" disabled={gpsState === "loading"} onClick={() => void handleCurrentLocation()}><span aria-hidden="true">⌖</span>{gpsState === "loading" ? t("location.finding") : t("location.useCurrent")}</button>
    <div className={gpsState === "error" ? "location-status error" : "location-status"} aria-live="polite">{gpsState === "success" && t("location.gpsSuccess")}{gpsState === "error" && t("location.gpsError")}</div>
    <div className="location-divider"><span>{t("location.or")}</span></div>

    {mapState !== "failed" ? <>
      <label className={mapState === "ready" ? "places-search" : "places-search pending"} htmlFor="places-search-input"><span id="places-label">{t("location.searchLabel")}</span><input id="places-search-input" type="search" role="combobox" aria-autocomplete="list" autoComplete="off" placeholder={t("location.searchPlaceholder")} value={searchText} aria-controls="places-suggestions" aria-expanded={suggestions.length > 0} aria-describedby={searchState === "failed" ? "places-search-error" : undefined} onChange={(event) => setSearchText(event.target.value)} />{searchState === "loading" && <small className="field-hint" role="status">{t("location.searching")}</small>}{searchState === "failed" && <small className="field-error" id="places-search-error" role="alert">{t("location.searchFailed")}</small>}{suggestions.length > 0 && <ul className="places-suggestions" id="places-suggestions" role="listbox">{suggestions.map((prediction) => <li key={prediction.placeId} role="option" aria-selected="false"><button type="button" onClick={() => void selectPlace(prediction)}><strong>{prediction.mainText?.text ?? prediction.text.text}</strong>{prediction.secondaryText?.text && <span>{prediction.secondaryText.text}</span>}</button></li>)}</ul>}</label>
      <div className={hasCoordinates ? "map-preview visible" : "map-preview"} aria-busy={mapIsPending}><div ref={mapElement} className="map-canvas" aria-label={t("location.mapLabel")} />{mapIsPending && <div className="map-loading" role="status"><span className="spinner dark" /> {t("location.loadingMap")}</div>}</div>
    </> : <div className="inline-notice map-fallback" role="status"><strong>{t("location.mapUnavailable")}</strong><span>{t("location.mapFallback")}</span></div>}

    {hasCoordinates && <p className="pin-hint">{mapState === "ready" ? t("location.pinTap") : t("location.coordinatesSaved")}</p>}
    {errors.location && <span className="field-error" role="alert">{errors.location}</span>}
    <label><span>{t("location.address")}</span><textarea rows={3} placeholder={t("location.addressPlaceholder")} value={location.written_address} aria-invalid={!!errors.written_address} aria-describedby={errors.written_address ? "address-error" : undefined} onChange={(event) => onFieldChange("written_address", event.target.value)} />{errors.written_address && <span className="field-error" id="address-error" role="alert">{errors.written_address}</span>}</label>
    <label><span>{t("location.notes")} <em>{t("location.required")}</em></span><textarea required rows={2} placeholder={t("location.notesPlaceholder")} value={location.instructions} aria-invalid={!!errors.instructions} aria-describedby={errors.instructions ? "instructions-error" : undefined} onChange={(event) => onFieldChange("instructions", event.target.value)} />{errors.instructions && <span className="field-error" id="instructions-error" role="alert">{errors.instructions}</span>}</label>
    <details className="manual-map-link"><summary>{t("location.manualToggle")}</summary><label><span>{t("location.manualLabel")}</span><input type="url" placeholder="https://maps.app.goo.gl/…" value={location.location_url} aria-invalid={!!errors.location_url} aria-describedby={errors.location_url ? "map-error" : "map-hint"} onChange={(event) => onFieldChange("location_url", event.target.value)} /><small id="map-hint" className="field-hint">{t("location.manualHint")}</small>{errors.location_url && <span className="field-error" id="map-error" role="alert">{errors.location_url}</span>}</label></details>
  </div>;
}

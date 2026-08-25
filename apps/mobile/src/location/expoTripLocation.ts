import * as Location from "expo-location";
import type { TripLocationSource } from "./startTripLocation";

const LAST_KNOWN_MAX_AGE_MS = 60_000;
const LAST_KNOWN_MAX_ACCURACY_METERS = 500;

export const expoTripLocationSource: TripLocationSource = {
  getPermission: Location.getForegroundPermissionsAsync,
  requestPermission: Location.requestForegroundPermissionsAsync,
  getLastKnown: () =>
    Location.getLastKnownPositionAsync({
      maxAge: LAST_KNOWN_MAX_AGE_MS,
      requiredAccuracy: LAST_KNOWN_MAX_ACCURACY_METERS,
    }),
  getCurrent: () =>
    Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }),
};

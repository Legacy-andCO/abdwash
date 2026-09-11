import type { TripLocationSource } from "./startTripLocation";

export const expoTripLocationSource: TripLocationSource = {
  // Ask through getCurrentPosition so the prompt is covered by the existing
  // trip timeout, including browsers without the Permissions query API.
  getPermission: async () => ({ granted: Boolean(navigator.geolocation), canAskAgain: false }),
  requestPermission: async () => ({ granted: Boolean(navigator.geolocation) }),
  getLastKnown: async () => null,
  getCurrent: () => new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: false, maximumAge: 60_000, timeout: 8_000,
    });
  }),
};

export type TripOrigin = { latitude: number; longitude: number };
export type TripLocationFailure =
  | "LOCATION_PERMISSION_DENIED"
  | "LOCATION_TIMEOUT"
  | "LOCATION_UNAVAILABLE";

type Permission = { granted: boolean; canAskAgain?: boolean };
type Position = {
  timestamp: number;
  coords: {
    latitude: number;
    longitude: number;
    accuracy?: number | null;
  };
};

export type TripLocationSource = {
  getPermission: () => Promise<Permission>;
  requestPermission: () => Promise<Permission>;
  getLastKnown: () => Promise<Position | null>;
  getCurrent: () => Promise<Position>;
};

export type TripLocationResult =
  | { origin: TripOrigin; source: "last_known" | "current" }
  | { origin: null; failure: TripLocationFailure };

const LAST_KNOWN_MAX_AGE_MS = 60_000;
const LAST_KNOWN_MAX_ACCURACY_METERS = 500;

function usableLastKnown(position: Position | null, now: number) {
  if (!position || now - position.timestamp > LAST_KNOWN_MAX_AGE_MS)
    return false;
  return (
    position.coords.accuracy == null ||
    position.coords.accuracy <= LAST_KNOWN_MAX_ACCURACY_METERS
  );
}

function originOf(position: Position): TripOrigin {
  return {
    latitude: position.coords.latitude,
    longitude: position.coords.longitude,
  };
}

export async function acquireTripOrigin(
  source: TripLocationSource,
  timeoutMs = 9_000,
  now = Date.now(),
): Promise<TripLocationResult> {
  let permission: Permission;
  try {
    permission = await source.getPermission();
    if (!permission.granted && permission.canAskAgain !== false)
      permission = await source.requestPermission();
  } catch {
    return { origin: null, failure: "LOCATION_UNAVAILABLE" };
  }
  if (!permission.granted)
    return { origin: null, failure: "LOCATION_PERMISSION_DENIED" };

  const lastKnown = await source.getLastKnown().catch(() => null);
  if (usableLastKnown(lastKnown, now))
    return { origin: originOf(lastKnown as Position), source: "last_known" };

  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const current = await Promise.race([
      source.getCurrent(),
      new Promise<"timeout">((resolve) => {
        timer = setTimeout(() => resolve("timeout"), timeoutMs);
      }),
    ]);
    if (current === "timeout")
      return { origin: null, failure: "LOCATION_TIMEOUT" };
    return { origin: originOf(current), source: "current" };
  } catch {
    return { origin: null, failure: "LOCATION_UNAVAILABLE" };
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export function tripLocationFailureMessage(failure: TripLocationFailure) {
  if (failure === "LOCATION_PERMISSION_DENIED")
    return "Location permission is required for ETA.";
  if (failure === "LOCATION_TIMEOUT")
    return "We couldn't get your location before the timeout.";
  return "We couldn't get your location.";
}

type MapsEnvironment = {
  document: Document;
  window: Window & typeof globalThis;
};

const scriptId = "trifecta-google-maps";
const readinessIntervalMs = 75;
const readinessTimeoutMs = 15_000;
let loaderPromise: Promise<typeof google> | null = null;

function mapsAreAvailable(environment: MapsEnvironment): boolean {
  return typeof environment.window.google?.maps?.importLibrary === "function";
}

function browserEnvironment(): MapsEnvironment | null {
  if (typeof window === "undefined" || typeof document === "undefined") return null;
  return { window, document };
}

export function loadGoogleMaps(
  apiKey: string | undefined,
  environment = browserEnvironment(),
): Promise<typeof google> {
  if (!environment) return Promise.reject(new Error("Google Maps can only load in a browser."));
  if (mapsAreAvailable(environment)) {
    return Promise.resolve(environment.window.google);
  }
  if (!apiKey) return Promise.reject(new Error("Google Maps is not configured."));
  if (loaderPromise) return loaderPromise;

  loaderPromise = new Promise<typeof google>((resolve, reject) => {
    const existing = (environment.document.getElementById(scriptId)
      ?? environment.document.querySelector('script[src^="https://maps.googleapis.com/maps/api/js"]')) as HTMLScriptElement | null;
    const script = existing ?? environment.document.createElement("script");
    const ownsScript = existing === null;
    let readinessTimer: number | undefined;
    let timeout: number | undefined;
    let settled = false;

    const checkReadiness = () => {
      if (settled) return;
      if (mapsAreAvailable(environment)) {
        settled = true;
        cleanup();
        resolve(environment.window.google);
        return;
      }
      if (readinessTimer !== undefined) environment.window.clearTimeout(readinessTimer);
      readinessTimer = environment.window.setTimeout(checkReadiness, readinessIntervalMs);
    };
    const settleFailed = (message: string, removeOwnedScript = false) => {
      if (settled) return;
      settled = true;
      cleanup();
      if (removeOwnedScript && ownsScript) script.remove();
      loaderPromise = null;
      reject(new Error(message));
    };
    const cleanup = () => {
      if (timeout !== undefined) environment.window.clearTimeout(timeout);
      if (readinessTimer !== undefined) environment.window.clearTimeout(readinessTimer);
      script.removeEventListener("load", checkReadiness);
      script.removeEventListener("error", handleScriptError);
    };
    const handleScriptError = () => settleFailed("Google Maps failed to load.", true);

    script.addEventListener("load", checkReadiness, { once: true });
    script.addEventListener("error", handleScriptError, { once: true });
    timeout = environment.window.setTimeout(() => {
      settleFailed("Google Maps readiness timed out.");
    }, readinessTimeoutMs);

    if (ownsScript) {
      const parameters = new URLSearchParams({ key: apiKey, v: "weekly", loading: "async" });
      script.id = scriptId;
      script.async = true;
      script.src = `https://maps.googleapis.com/maps/api/js?${parameters}`;
      environment.document.head.append(script);
    }
    checkReadiness();
  });

  return loaderPromise;
}

export function resetGoogleMapsLoaderForTests() {
  loaderPromise = null;
}

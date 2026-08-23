type MapsEnvironment = {
  document: Document;
  window: Window & typeof globalThis;
};

const scriptId = "abdwash-google-maps";
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
    const timeout = environment.window.setTimeout(() => settleFailed(), 15_000);

    const settleLoaded = () => {
      cleanup();
      if (mapsAreAvailable(environment)) {
        resolve(environment.window.google);
        return;
      }
      loaderPromise = null;
      reject(new Error("Google Maps loaded without an available Maps API."));
    };
    const settleFailed = () => {
      cleanup();
      script.remove();
      loaderPromise = null;
      reject(new Error("Google Maps failed to load."));
    };
    const cleanup = () => {
      environment.window.clearTimeout(timeout);
      script.removeEventListener("load", settleLoaded);
      script.removeEventListener("error", settleFailed);
    };

    script.addEventListener("load", settleLoaded, { once: true });
    script.addEventListener("error", settleFailed, { once: true });

    if (!existing) {
      const parameters = new URLSearchParams({ key: apiKey, v: "weekly", loading: "async" });
      script.id = scriptId;
      script.async = true;
      script.src = `https://maps.googleapis.com/maps/api/js?${parameters}`;
      environment.document.head.append(script);
    } else if (mapsAreAvailable(environment)) {
      settleLoaded();
    }
  });

  return loaderPromise;
}

export function resetGoogleMapsLoaderForTests() {
  loaderPromise = null;
}

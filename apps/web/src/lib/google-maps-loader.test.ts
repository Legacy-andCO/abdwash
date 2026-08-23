// @vitest-environment jsdom

import { afterEach, describe, expect, it } from "vitest";
import { loadGoogleMaps, resetGoogleMapsLoaderForTests } from "./google-maps-loader";

function setGoogle(value?: typeof google) {
  Object.defineProperty(window, "google", { configurable: true, writable: true, value });
}

function usableGoogle() {
  return { maps: { importLibrary: () => Promise.resolve({}) } } as unknown as typeof google;
}

afterEach(() => {
  document.querySelectorAll('script[src^="https://maps.googleapis.com/maps/api/js"], #abdwash-google-maps').forEach((script) => script.remove());
  setGoogle(undefined);
  resetGoogleMapsLoaderForTests();
});

describe("shared Google Maps loader", () => {
  it("starts one script load and shares the same promise between callers", async () => {
    const first = loadGoogleMaps("public-test-key");
    const second = loadGoogleMaps("public-test-key");
    expect(second).toBe(first);
    const script = document.getElementById("abdwash-google-maps") as HTMLScriptElement;
    expect(document.querySelectorAll("#abdwash-google-maps")).toHaveLength(1);
    expect(script.src).toContain("maps.googleapis.com/maps/api/js");
    setGoogle(usableGoogle());
    script.dispatchEvent(new Event("load"));
    await expect(first).resolves.toBe(window.google);
  });

  it("resolves immediately without injecting a script when Maps is already loaded", async () => {
    const loaded = usableGoogle();
    setGoogle(loaded);
    await expect(loadGoogleMaps("public-test-key")).resolves.toBe(loaded);
    expect(document.getElementById("abdwash-google-maps")).toBeNull();
  });

  it("reuses a Maps script that another component already started", async () => {
    const existing = document.createElement("script");
    existing.src = "https://maps.googleapis.com/maps/api/js?key=already-present";
    document.head.append(existing);
    const loading = loadGoogleMaps("public-test-key");
    expect(document.querySelectorAll('script[src^="https://maps.googleapis.com/maps/api/js"]')).toHaveLength(1);
    setGoogle(usableGoogle());
    existing.dispatchEvent(new Event("load"));
    await expect(loading).resolves.toBe(window.google);
  });

  it("rejects cleanly, removes its failed script, and permits a later retry", async () => {
    const loading = loadGoogleMaps("public-test-key");
    document.getElementById("abdwash-google-maps")?.dispatchEvent(new Event("error"));
    await expect(loading).rejects.toThrow("failed to load");
    expect(document.getElementById("abdwash-google-maps")).toBeNull();
    expect(loadGoogleMaps("public-test-key")).not.toBe(loading);
  });

  it("does not remove an existing global script when the loader state is reset", () => {
    const script = document.createElement("script");
    script.id = "abdwash-google-maps";
    document.head.append(script);
    resetGoogleMapsLoaderForTests();
    expect(document.getElementById("abdwash-google-maps")).toBe(script);
  });
});

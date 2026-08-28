// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { loadGoogleMaps, resetGoogleMapsLoaderForTests } from "./google-maps-loader";

function setGoogle(value?: typeof google) {
  Object.defineProperty(window, "google", { configurable: true, writable: true, value });
}

function usableGoogle() {
  return { maps: { importLibrary: () => Promise.resolve({}) } } as unknown as typeof google;
}

function existingMapsScript() {
  const script = document.createElement("script");
  script.src = "https://maps.googleapis.com/maps/api/js?key=already-present";
  document.head.append(script);
  return script;
}

afterEach(() => {
  vi.useRealTimers();
  document.querySelectorAll('script[src^="https://maps.googleapis.com/maps/api/js"], #trifecta-google-maps').forEach((script) => script.remove());
  setGoogle(undefined);
  resetGoogleMapsLoaderForTests();
});

describe("shared Google Maps loader", () => {
  it("waits after a new script load until importLibrary becomes available", async () => {
    vi.useFakeTimers();
    const loading = loadGoogleMaps("public-test-key");
    const script = document.getElementById("trifecta-google-maps") as HTMLScriptElement;
    script.dispatchEvent(new Event("load"));
    await vi.advanceTimersByTimeAsync(100);
    setGoogle(usableGoogle());
    await vi.advanceTimersByTimeAsync(75);
    await expect(loading).resolves.toBe(window.google);
  });

  it("polls an existing script even when its load event already fired", async () => {
    vi.useFakeTimers();
    const existing = existingMapsScript();
    existing.dispatchEvent(new Event("load"));
    const loading = loadGoogleMaps("public-test-key");
    setGoogle(usableGoogle());
    await vi.advanceTimersByTimeAsync(75);
    await expect(loading).resolves.toBe(window.google);
    expect(document.querySelectorAll('script[src^="https://maps.googleapis.com/maps/api/js"]')).toHaveLength(1);
  });

  it("resolves immediately without injecting a script when Maps is already available", async () => {
    const loaded = usableGoogle();
    setGoogle(loaded);
    await expect(loadGoogleMaps("public-test-key")).resolves.toBe(loaded);
    expect(document.querySelector('script[src^="https://maps.googleapis.com/maps/api/js"]')).toBeNull();
  });

  it("shares one promise and injects only one script for simultaneous callers", async () => {
    const first = loadGoogleMaps("public-test-key");
    const second = loadGoogleMaps("public-test-key");
    expect(second).toBe(first);
    expect(document.querySelectorAll("#trifecta-google-maps")).toHaveLength(1);
    setGoogle(usableGoogle());
    document.getElementById("trifecta-google-maps")?.dispatchEvent(new Event("load"));
    await expect(first).resolves.toBe(window.google);
  });

  it("rejects after a bounded readiness timeout", async () => {
    vi.useFakeTimers();
    existingMapsScript();
    const loading = loadGoogleMaps("public-test-key");
    const rejection = expect(loading).rejects.toThrow("readiness timed out");
    await vi.advanceTimersByTimeAsync(15_000);
    await rejection;
  });

  it("does not remove a pre-existing script on readiness timeout", async () => {
    vi.useFakeTimers();
    const existing = existingMapsScript();
    const loading = loadGoogleMaps("public-test-key");
    const rejection = expect(loading).rejects.toThrow("readiness timed out");
    await vi.advanceTimersByTimeAsync(15_000);
    await rejection;
    expect(existing.isConnected).toBe(true);
  });

  it("clears the failed shared promise so a later call can succeed", async () => {
    const failed = loadGoogleMaps("public-test-key");
    const failedScript = document.getElementById("trifecta-google-maps") as HTMLScriptElement;
    failedScript.dispatchEvent(new Event("error"));
    await expect(failed).rejects.toThrow("failed to load");
    expect(failedScript.isConnected).toBe(false);

    const retry = loadGoogleMaps("public-test-key");
    expect(retry).not.toBe(failed);
    setGoogle(usableGoogle());
    document.getElementById("trifecta-google-maps")?.dispatchEvent(new Event("load"));
    await expect(retry).resolves.toBe(window.google);
  });
});

// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createClient } from "@supabase/supabase-js";
import { authStorage } from "./authStorage.web";
import { Alert } from "./alert.web";
import { expoTripLocationSource } from "./location/expoTripLocation.web";
import { acquireTripOrigin } from "./location/startTripLocation";

beforeEach(() => {
  // jsdom does not implement the browser dialog top-layer methods.
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; };
});

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.replaceChildren();
  localStorage.clear();
});

describe("browser adapters", () => {
  it("persists a Supabase password session, restores it, refreshes it and removes it on logout", async () => {
    vi.stubGlobal("BroadcastChannel", undefined);
    const token = (name) => `eyJhbGciOiJIUzI1NiJ9.${btoa(JSON.stringify({ sub: "staff-1", exp: Math.floor(Date.now() / 1000) + 3600, name }))}.signature`;
    const response = (name) => ({ access_token: token(name), refresh_token: `${name}-refresh`, expires_in: 3600, token_type: "bearer", user: { id: "staff-1" } });
    const fetch = vi.fn(async (url) => String(url).includes("logout")
      ? new Response(null, { status: 204 })
      : new Response(JSON.stringify(response(String(url).includes("refresh_token") ? "refreshed" : "login")), { status: 200, headers: { "Content-Type": "application/json" } }));
    const options = {
      global: { fetch },
      auth: { storage: authStorage, storageKey: "staff-browser-test", persistSession: true, autoRefreshToken: false, detectSessionInUrl: false },
    };
    const first = createClient("https://test.supabase.co", "public-test-key", options);
    const signedIn = await first.auth.signInWithPassword({ email: "staff@example.com", password: "test-password" });
    expect(signedIn.error).toBeNull();
    expect(JSON.parse(localStorage.getItem("staff-browser-test")).refresh_token).toBe("login-refresh");
    const restored = createClient("https://test.supabase.co", "public-test-key", options);
    expect((await restored.auth.getSession()).data.session.access_token).toBe(token("login"));
    expect((await restored.auth.refreshSession()).error).toBeNull();
    expect(JSON.parse(localStorage.getItem("staff-browser-test")).refresh_token).toBe("refreshed-refresh");
    expect((await restored.auth.signOut()).error).toBeNull();
    expect(localStorage.getItem("staff-browser-test")).toBeNull();
    expect((await first.auth.getSession()).data.session).toBeNull();
    await first.auth.stopAutoRefresh();
    await restored.auth.stopAutoRefresh();
  });

  it("requires explicit confirmation and keeps every action label", () => {
    const confirm = vi.fn();
    const cancel = vi.fn();
    Alert.alert("Remove saved vehicle?", "<vehicle>", [
      { text: "Cancel", style: "cancel", onPress: cancel },
      { text: "Remove", style: "destructive", onPress: confirm },
    ]);
    expect(confirm).not.toHaveBeenCalled();
    const dialog = document.querySelector("dialog");
    expect(dialog.open).toBe(true);
    expect(dialog.querySelector("p").textContent).toBe("<vehicle>");
    expect(dialog.querySelectorAll("button")[1].textContent).toBe("Remove");
    dialog.querySelector("button").click();
    expect(cancel).toHaveBeenCalledOnce();
    expect(confirm).not.toHaveBeenCalled();
    Alert.alert("Confirm", undefined, [{ text: "Save", onPress: confirm }]);
    document.querySelector("button").click();
    expect(confirm).toHaveBeenCalledOnce();
    expect(document.querySelector("dialog")).toBeNull();
  });

  it("gets browser coordinates and falls back safely when location is denied", async () => {
    const getCurrentPosition = vi.fn((resolve) => resolve({ timestamp: Date.now(), coords: { latitude: 25, longitude: 55 } }));
    vi.stubGlobal("navigator", { geolocation: { getCurrentPosition } });
    expect((await acquireTripOrigin(expoTripLocationSource)).origin).toEqual({ latitude: 25, longitude: 55 });
    expect(getCurrentPosition.mock.calls[0][2].timeout).toBe(8000);
    getCurrentPosition.mockImplementation((_resolve, reject) => reject({ code: 1 }));
    expect((await acquireTripOrigin(expoTripLocationSource)).origin).toBeNull();
    vi.stubGlobal("navigator", {});
    expect((await acquireTripOrigin(expoTripLocationSource)).origin).toBeNull();
  });
});

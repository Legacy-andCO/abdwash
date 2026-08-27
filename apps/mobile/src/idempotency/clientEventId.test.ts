import { afterEach, describe, expect, it, vi } from "vitest";

const uuidState = vi.hoisted(() => ({ next: 0 }));
vi.mock("expo-crypto", () => ({
  randomUUID: () =>
    `123e4567-e89b-42d3-a456-${String(++uuidState.next).padStart(12, "0")}`,
}));

import { ApiError } from "../errors/domainErrors";
import { ClientEventIdStore, newClientEventId } from "./clientEventId";

afterEach(() => vi.restoreAllMocks());

describe("mobile client event IDs", () => {
  it("generates a UUID without relying on global crypto.randomUUID", () => {
    const original = globalThis.crypto;
    Object.defineProperty(globalThis, "crypto", {
      configurable: true,
      value: undefined,
    });
    try {
      expect(newClientEventId()).toMatch(
        /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
      );
    } finally {
      Object.defineProperty(globalThis, "crypto", {
        configurable: true,
        value: original,
      });
    }
  });

  it("retains an ID after an uncertain failure and clears it after success", () => {
    const store = new ClientEventIdStore();
    const first = store.get("job:start-trip");
    store.failed("job:start-trip", new ApiError("OFFLINE", 0));
    expect(store.get("job:start-trip")).toBe(first);
    store.succeeded("job:start-trip");
    expect(store.get("job:start-trip")).not.toBe(first);
  });

  it("clears an ID after a definitive rejection", () => {
    const store = new ClientEventIdStore();
    const first = store.get("job:complete");
    store.failed("job:complete", new ApiError("INVALID_STATE", 409));
    expect(store.get("job:complete")).not.toBe(first);
  });
});

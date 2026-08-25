import { afterEach, describe, expect, it, vi } from "vitest";
import { RequestTimedOut, withRequestTimeout } from "./requestTimeout";

afterEach(() => vi.useRealTimers());

describe("withRequestTimeout", () => {
  it("aborts a normal API request after 15 seconds", async () => {
    vi.useFakeTimers();
    const operation = withRequestTimeout(
      (signal) =>
        new Promise<never>((_resolve, reject) => {
          signal.addEventListener("abort", () => reject(new Error("aborted")));
        }),
      undefined,
      15_000,
    );
    const expectation =
      expect(operation).rejects.toBeInstanceOf(RequestTimedOut);
    await vi.advanceTimersByTimeAsync(15_000);
    await expectation;
  });

  it("preserves a caller cancellation instead of reporting a timeout", async () => {
    const caller = new AbortController();
    const operation = withRequestTimeout(
      (signal) =>
        new Promise<never>((_resolve, reject) => {
          signal.addEventListener("abort", () =>
            reject(new Error("cancelled")),
          );
        }),
      caller.signal,
      20_000,
    );
    caller.abort();
    await expect(operation).rejects.toThrow("cancelled");
  });
});

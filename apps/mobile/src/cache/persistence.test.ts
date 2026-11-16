import { describe, expect, it, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import { prepareCachePreservingLogout } from "./logout";
import { retainedQueries } from "./persistence";

describe("multi-account operational persistence", () => {
  it("retains fresh queries from multiple scopes and prunes expired data", () => {
    const now = 10_000;
    const queries = [
      { queryKey: ["jobs", "business:manager:manager"], meta: { retentionMs: 5_000 }, state: { dataUpdatedAt: 9_000 } },
      { queryKey: ["jobs", "business:employee:employee"], meta: { retentionMs: 5_000 }, state: { dataUpdatedAt: 8_000 } },
      { queryKey: ["reports", "expired"], meta: { retentionMs: 1_000 }, state: { dataUpdatedAt: 1_000 } },
    ];
    expect(retainedQueries(queries, now, 5_000, 80).map((query) => query.queryKey[1])).toEqual([
      "business:manager:manager",
      "business:employee:employee",
    ]);
  });

  it("logout cancels activity and removes cached personal data from memory and disk", async () => {
    const clearQueries = vi.fn();
    const cancelQueries = vi.fn(async () => undefined);
    const clearMutations = vi.fn();
    await prepareCachePreservingLogout(
      {
        cancelQueries,
        getMutationCache: () => ({ clear: clearMutations }),
        clear: clearMutations,
      },
      clearQueries,
      async () => { clearQueries(); },
    );
    expect(clearQueries).toHaveBeenCalledTimes(2);
    expect(cancelQueries).toHaveBeenCalledOnce();
    expect(clearMutations).toHaveBeenCalledOnce();
  });

  it("removes sensitive queries on logout even when cancellation fails", async () => {
    const client = new QueryClient();
    client.setQueryData(["customer", "synthetic"], { address: "Private synthetic address" });
    const clearStorage = vi.fn(async () => undefined);
    client.cancelQueries = vi.fn(async () => { throw new Error("Synthetic cancellation failure"); });
    await expect(prepareCachePreservingLogout(client, vi.fn(), clearStorage)).rejects.toThrow();
    expect(client.getQueryData(["customer", "synthetic"])).toBeUndefined();
    expect(clearStorage).toHaveBeenCalledOnce();
  });

  it("serves a fresh revisit from memory with single-flight fetch behavior", async () => {
    const fetcher = vi.fn(async () => ({ items: ["cached"] }));
    const client = new QueryClient();
    const options = {
      queryKey: ["reports", "business:manager:manager", "week"],
      queryFn: fetcher,
      staleTime: 60_000,
    } as const;
    await Promise.all([client.fetchQuery(options), client.fetchQuery(options)]);
    await client.fetchQuery(options);
    expect(fetcher).toHaveBeenCalledOnce();

    await client.invalidateQueries({ queryKey: options.queryKey });
    await client.fetchQuery(options);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});

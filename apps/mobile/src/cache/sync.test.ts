import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";

const values = new Map<string, string>();
vi.mock("@react-native-async-storage/async-storage", () => ({
  default: {
    getItem: vi.fn((key: string) => Promise.resolve(values.get(key) ?? null)),
    setItem: vi.fn((key: string, value: string) => {
      values.set(key, value);
      return Promise.resolve();
    }),
  },
}));
vi.mock("../lib", () => ({ getSyncState: vi.fn() }));

import type { StaffContext, SyncState } from "../lib";
import {
  changedSyncDomains,
  queryPrefixesForDomains,
  synchronizeOperations,
  syncRevisionKey,
} from "./sync";

const context = {
  business_id: "business-1",
  staff_id: "staff-1",
  role: "manager",
} as StaffContext;
const state: SyncState = { jobs: 1, workforce: 2, schedule: 3, finance: 4 };

beforeEach(() => values.clear());

describe("revision-aware sync", () => {
  it("does no domain invalidation on initial or unchanged sync", async () => {
    const client = {
      invalidateQueries: vi.fn(
        async (_value: { queryKey: string[] }) => undefined,
      ),
    };
    expect(
      await synchronizeOperations(client as never, context, async () => state),
    ).toEqual([]);
    expect(
      await synchronizeOperations(client as never, context, async () => state),
    ).toEqual([]);
    expect(client.invalidateQueries).not.toHaveBeenCalled();
  });

  it("invalidates only query families affected by changed domains", async () => {
    values.set(syncRevisionKey(context), JSON.stringify(state));
    const client = {
      invalidateQueries: vi.fn(
        async (_value: { queryKey: string[] }) => undefined,
      ),
    };
    const next = { ...state, jobs: 2 };
    expect(
      await synchronizeOperations(client as never, context, async () => next),
    ).toEqual(["jobs"]);
    const prefixes = client.invalidateQueries.mock.calls.map(
      ([value]) => value.queryKey[0],
    );
    expect(prefixes).toEqual(queryPrefixesForDomains(["jobs"]));
    expect(
      client.invalidateQueries.mock.calls.every(
        ([value]) => value.queryKey[1] === "business-1:staff-1:manager",
      ),
    ).toBe(true);
    expect(prefixes).not.toContain("reports");
  });

  it("detects each revision independently", () => {
    expect(changedSyncDomains(state, { ...state, finance: 5 })).toEqual([
      "finance",
    ]);
  });

  it("keeps workforce refreshes away from finance reports", () => {
    const prefixes = queryPrefixesForDomains(["workforce"]);
    expect(prefixes).toContain("staff");
    expect(prefixes).toContain("shifts");
    expect(prefixes).not.toContain("reports");
  });

  it("retains cached content while a changed domain is marked stale", async () => {
    values.set(syncRevisionKey(context), JSON.stringify(state));
    const client = new QueryClient();
    const key = ["jobs", "business-1:staff-1:manager"];
    const otherScopeKey = ["jobs", "business-1:staff-2:employee"];
    client.setQueryData(key, { jobs: [{ id: "job-1" }] });
    client.setQueryData(otherScopeKey, { jobs: [{ id: "job-2" }] });

    await synchronizeOperations(client, context, async () => ({
      ...state,
      jobs: 2,
    }));

    expect(client.getQueryData(key)).toEqual({ jobs: [{ id: "job-1" }] });
    expect(client.getQueryState(key)?.isInvalidated).toBe(true);
    expect(client.getQueryState(otherScopeKey)?.isInvalidated).toBe(false);
  });
});

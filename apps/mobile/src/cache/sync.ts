import AsyncStorage from "@react-native-async-storage/async-storage";
import type { QueryClient } from "@tanstack/react-query";
import { getSyncState, type StaffContext, type SyncState } from "../lib";
import { operationalScope } from "./policy";

export type SyncDomain = keyof SyncState;
export const SYNC_REVISION_PREFIX = "abdwash:sync-revisions:v1:";

const domainPrefixes: Record<SyncDomain, string[]> = {
  jobs: ["jobs", "job", "quality", "dashboard", "teams", "team"],
  workforce: [
    "staff",
    "teams",
    "team",
    "shifts",
    "shift-assignments",
    "attendance",
    "attendance-history",
    "leave",
    "profile",
    "dashboard",
    "jobs",
  ],
  schedule: ["availability", "jobs", "job", "dashboard", "teams", "team"],
  finance: ["reports", "dashboard", "jobs", "job", "cancellations"],
  customers: ["customers", "customer", "loyalty-settings"],
};

export function changedSyncDomains(previous: SyncState, next: SyncState) {
  return (Object.keys(next) as SyncDomain[]).filter(
    (domain) => previous[domain] !== next[domain],
  );
}

export function queryPrefixesForDomains(domains: SyncDomain[]) {
  return [...new Set(domains.flatMap((domain) => domainPrefixes[domain]))];
}

export function syncRevisionKey(context: StaffContext) {
  return `${SYNC_REVISION_PREFIX}${operationalScope(context)}`;
}

export async function synchronizeOperations(
  client: QueryClient,
  context: StaffContext,
  fetchState = getSyncState,
) {
  const key = syncRevisionKey(context);
  const next = await fetchState();
  const stored = await AsyncStorage.getItem(key);
  if (!stored) {
    await AsyncStorage.setItem(key, JSON.stringify(next));
    return [] as SyncDomain[];
  }
  const previous = JSON.parse(stored) as SyncState;
  const domains = changedSyncDomains(previous, next);
  const scope = operationalScope(context);
  for (const prefix of queryPrefixesForDomains(domains)) {
    await client.invalidateQueries({
      queryKey: [prefix, scope],
      refetchType: "active",
    });
  }
  await AsyncStorage.setItem(key, JSON.stringify(next));
  if (typeof __DEV__ !== "undefined" && __DEV__ && domains.length) {
    console.info("[AbdWash Sync] revisions_changed", {
      previous,
      next,
      domains,
    });
  }
  return domains;
}

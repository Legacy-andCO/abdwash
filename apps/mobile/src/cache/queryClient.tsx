import AsyncStorage from "@react-native-async-storage/async-storage";
import { createAsyncStoragePersister } from "@tanstack/query-async-storage-persister";
import { focusManager, QueryClient } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import {
  removeOldestQuery,
  type PersistedClient,
} from "@tanstack/query-persist-client-core";
import { type PropsWithChildren, useEffect } from "react";
import { AppState, type AppStateStatus } from "react-native";
import { ApiError } from "../errors/domainErrors";
import { cancelInFlightWrites } from "../network/writeRegistry";
import { SYNC_REVISION_PREFIX } from "./sync";
import { prepareCachePreservingLogout } from "./logout";
import { retainedQueries } from "./persistence";
export { cacheTimes, queryKeys } from "./policy";

export const OPERATIONAL_CACHE_KEY = "abdwash:operations-query-cache:v3";
const INCOMPATIBLE_CACHE_KEYS = [
  "abdwash:operations-query-cache:v1",
  "abdwash:operations-query-cache:v2",
];
const CACHE_BUSTER = "operations-v3-role-scoped";
const MAX_PERSISTED_QUERIES = 80;
const MAX_CACHE_BYTES = 2_000_000;
const MAX_RETENTION_MS = 7 * 24 * 60 * 60_000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      gcTime: MAX_RETENTION_MS,
      retry: (attempt, error) =>
        !(
          error instanceof ApiError &&
          error.status >= 400 &&
          error.status < 500
        ) && attempt < 2,
      refetchOnReconnect: false,
      refetchOnWindowFocus: false,
      refetchOnMount: (query) => query.state.isInvalidated,
    },
    mutations: { retry: false },
  },
});

const persister = createAsyncStoragePersister({
  storage: AsyncStorage,
  key: OPERATIONAL_CACHE_KEY,
  throttleTime: 1_000,
  serialize: (client) => {
    const now = Date.now();
    const pruned: PersistedClient = {
      ...client,
      clientState: {
        ...client.clientState,
        queries: retainedQueries(
          client.clientState.queries,
          now,
          MAX_RETENTION_MS,
          MAX_PERSISTED_QUERIES,
        ),
      },
    };
    const serialized = JSON.stringify(pruned);
    if (serialized.length > MAX_CACHE_BYTES)
      throw new Error("CACHE_SIZE_LIMIT");
    return serialized;
  },
  retry: removeOldestQuery,
});

function onAppStateChange(status: AppStateStatus) {
  focusManager.setFocused(status === "active");
}

export function OperationsCacheProvider({ children }: PropsWithChildren) {
  useEffect(() => {
    void AsyncStorage.multiRemove(INCOMPATIBLE_CACHE_KEYS);
    const subscription = AppState.addEventListener("change", onAppStateChange);
    return () => subscription.remove();
  }, []);
  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister,
        maxAge: MAX_RETENTION_MS,
        buster: CACHE_BUSTER,
        dehydrateOptions: {
          shouldDehydrateQuery: (query) =>
            query.state.status === "success" && query.meta?.persist === true,
        },
      }}
    >
      {children}
    </PersistQueryClientProvider>
  );
}

export async function prepareOperationalLogout() {
  await prepareCachePreservingLogout(queryClient, cancelInFlightWrites);
}

export async function clearOperationalCache() {
  queryClient.clear();
  const keys = await AsyncStorage.getAllKeys();
  await AsyncStorage.multiRemove(
    keys.filter(
      (key) =>
        key === OPERATIONAL_CACHE_KEY || key.startsWith(SYNC_REVISION_PREFIX),
    ),
  );
}

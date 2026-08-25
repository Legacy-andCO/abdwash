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
import { SYNC_REVISION_PREFIX } from "./sync";
export { cacheTimes, queryKeys } from "./policy";

export const OPERATIONAL_CACHE_KEY = "abdwash:operations-query-cache:v2";
const OLD_OPERATIONAL_CACHE_KEY = "abdwash:operations-query-cache:v1";
const CACHE_BUSTER = "operations-v2";
const MAX_PERSISTED_QUERIES = 80;
const MAX_CACHE_BYTES = 2_000_000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      gcTime: 12 * 60 * 60_000,
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
    const pruned: PersistedClient = {
      ...client,
      clientState: {
        ...client.clientState,
        queries: [...client.clientState.queries]
          .sort(
            (left, right) =>
              right.state.dataUpdatedAt - left.state.dataUpdatedAt,
          )
          .slice(0, MAX_PERSISTED_QUERIES),
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
    void AsyncStorage.removeItem(OLD_OPERATIONAL_CACHE_KEY);
    const subscription = AppState.addEventListener("change", onAppStateChange);
    return () => subscription.remove();
  }, []);
  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister,
        maxAge: 12 * 60 * 60_000,
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

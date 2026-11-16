import AsyncStorage from "@react-native-async-storage/async-storage";
import { focusManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type PropsWithChildren, useEffect } from "react";
import { AppState, type AppStateStatus } from "react-native";
import { ApiError } from "../errors/domainErrors";
import { cancelInFlightWrites } from "../network/writeRegistry";
import { SYNC_REVISION_PREFIX } from "./sync";
import { prepareCachePreservingLogout } from "./logout";
export { cacheTimes, queryKeys } from "./policy";

export const OPERATIONAL_CACHE_KEY = "abdwash:operations-query-cache:v3";
const INCOMPATIBLE_CACHE_KEYS = [
  "abdwash:operations-query-cache:v1",
  "abdwash:operations-query-cache:v2",
];
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

function onAppStateChange(status: AppStateStatus) {
  focusManager.setFocused(status === "active");
}

export function OperationsCacheProvider({ children }: PropsWithChildren) {
  useEffect(() => {
    void clearPersistedOperationalCache();
    const subscription = AppState.addEventListener("change", onAppStateChange);
    return () => subscription.remove();
  }, []);
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}

export async function prepareOperationalLogout() {
  await prepareCachePreservingLogout(queryClient, cancelInFlightWrites, clearPersistedOperationalCache);
}

export async function clearOperationalCache() {
  queryClient.clear();
  await clearPersistedOperationalCache();
}

async function clearPersistedOperationalCache() {
  const keys = await AsyncStorage.getAllKeys();
  await AsyncStorage.multiRemove(
    keys.filter(
      (key) =>
        key === OPERATIONAL_CACHE_KEY || INCOMPATIBLE_CACHE_KEYS.includes(key) || key.startsWith(SYNC_REVISION_PREFIX),
    ),
  );
}

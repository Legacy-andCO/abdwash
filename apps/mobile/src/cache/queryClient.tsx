import AsyncStorage from "@react-native-async-storage/async-storage";
import { createAsyncStoragePersister } from "@tanstack/query-async-storage-persister";
import { focusManager, QueryClient } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { type PropsWithChildren, useEffect } from "react";
import { AppState, type AppStateStatus } from "react-native";
import { ApiError } from "../errors/domainErrors";
export { cacheTimes, queryKeys } from "./policy";

export const OPERATIONAL_CACHE_KEY = "abdwash:operations-query-cache:v1";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      gcTime: 24 * 60 * 60_000,
      retry: (attempt, error) =>
        !(
          error instanceof ApiError &&
          error.status >= 400 &&
          error.status < 500
        ) && attempt < 2,
      refetchOnReconnect: true,
      refetchOnWindowFocus: true,
    },
    mutations: { retry: false },
  },
});

const persister = createAsyncStoragePersister({
  storage: AsyncStorage,
  key: OPERATIONAL_CACHE_KEY,
  throttleTime: 1_000,
});

function onAppStateChange(status: AppStateStatus) {
  focusManager.setFocused(status === "active");
}

export function OperationsCacheProvider({ children }: PropsWithChildren) {
  useEffect(() => {
    const subscription = AppState.addEventListener("change", onAppStateChange);
    return () => subscription.remove();
  }, []);
  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister,
        maxAge: 24 * 60 * 60_000,
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
  await AsyncStorage.removeItem(OPERATIONAL_CACHE_KEY);
}

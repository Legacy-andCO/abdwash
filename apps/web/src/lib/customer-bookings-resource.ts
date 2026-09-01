import { getCustomerBookings } from "./api";
import type { CustomerBookingSummary } from "./types";

const FRESHNESS_MS = 20_000;
const entries = new Map<
  string,
  {
    data?: CustomerBookingSummary[];
    fetchedAt?: number;
    promise?: Promise<CustomerBookingSummary[]>;
  }
>();

export function cachedCustomerBookings(userId: string) {
  return entries.get(userId)?.data ?? null;
}

export function clearCachedCustomerBookings(userId: string) {
  entries.delete(userId);
}

export function loadCustomerBookings(
  userId: string,
  options: { refresh?: boolean } = {},
) {
  const entry = entries.get(userId);
  if (entry?.promise) return entry.promise;
  if (
    !options.refresh &&
    entry?.data &&
    entry.fetchedAt &&
    Date.now() - entry.fetchedAt < FRESHNESS_MS
  ) {
    return Promise.resolve(entry.data);
  }
  const promise = getCustomerBookings()
    .then((data) => {
      entries.set(userId, { data, fetchedAt: Date.now() });
      return data;
    })
    .finally(() => {
      const current = entries.get(userId);
      if (current?.promise === promise) delete current.promise;
    });
  entries.set(userId, { ...entry, promise });
  return promise;
}

export function resetCustomerBookingsResourceForTests() {
  entries.clear();
}

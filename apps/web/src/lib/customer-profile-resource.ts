import { getCustomerProfile } from "./api";
import type { CustomerProfileBootstrap } from "./types";

const FRESHNESS_MS = 60_000;
const entries = new Map<
  string,
  {
    data?: CustomerProfileBootstrap;
    fetchedAt?: number;
    promise?: Promise<CustomerProfileBootstrap>;
  }
>();

export function cachedCustomerProfile(userId: string) {
  return entries.get(userId)?.data ?? null;
}

export function setCachedCustomerProfile(
  userId: string,
  data: CustomerProfileBootstrap,
) {
  entries.set(userId, { data, fetchedAt: Date.now() });
}

export function clearCachedCustomerProfile(userId: string) {
  entries.delete(userId);
}

export function loadCustomerProfile(
  userId: string,
  options: { refresh?: boolean } = {},
): Promise<CustomerProfileBootstrap> {
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

  const promise = getCustomerProfile()
    .then((data) => {
      setCachedCustomerProfile(userId, data);
      return data;
    })
    .finally(() => {
      const current = entries.get(userId);
      if (current?.promise === promise) delete current.promise;
    });
  entries.set(userId, { ...entry, promise });
  return promise;
}

export function resetCustomerProfileResourceForTests() {
  entries.clear();
}

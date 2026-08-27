import * as Crypto from "expo-crypto";

import { ApiError } from "../errors/domainErrors";

export function newClientEventId(): string {
  return Crypto.randomUUID();
}

export function isUncertainMutationFailure(error: unknown): boolean {
  return (
    !(error instanceof ApiError) || error.status === 0 || error.status >= 500
  );
}

export class ClientEventIdStore {
  private readonly ids = new Map<string, string>();

  get(key: string): string {
    const existing = this.ids.get(key);
    if (existing) return existing;
    const created = newClientEventId();
    this.ids.set(key, created);
    return created;
  }

  succeeded(key: string): void {
    this.ids.delete(key);
  }

  failed(key: string, error: unknown): void {
    if (!isUncertainMutationFailure(error)) this.ids.delete(key);
  }
}

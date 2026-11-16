type LogoutQueryClient = {
  cancelQueries: () => Promise<unknown>;
  getMutationCache: () => { clear: () => void };
  clear: () => void;
};

export async function prepareCachePreservingLogout(
  client: LogoutQueryClient,
  cancelWrites: () => void,
  clearStorage: () => Promise<void>,
) {
  cancelWrites();
  try {
    await client.cancelQueries();
  } finally {
    client.clear();
    await clearStorage();
  }
}

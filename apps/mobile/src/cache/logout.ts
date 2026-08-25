type LogoutQueryClient = {
  cancelQueries: () => Promise<unknown>;
  getMutationCache: () => { clear: () => void };
};

export async function prepareCachePreservingLogout(
  client: LogoutQueryClient,
  cancelWrites: () => void,
) {
  cancelWrites();
  await client.cancelQueries();
  client.getMutationCache().clear();
}

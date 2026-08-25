const activeWrites = new Set<AbortController>();

export function beginTrackedWrite() {
  const controller = new AbortController();
  activeWrites.add(controller);
  return {
    signal: controller.signal,
    release: () => activeWrites.delete(controller),
  };
}

export function cancelInFlightWrites() {
  for (const controller of activeWrites) controller.abort();
  activeWrites.clear();
}

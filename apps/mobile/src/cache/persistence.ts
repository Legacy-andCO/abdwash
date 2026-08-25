export type RetainedQuery = {
  meta?: Record<string, unknown>;
  state: { dataUpdatedAt: number };
};

export function retainedQueries<T extends RetainedQuery>(
  queries: T[],
  now: number,
  defaultRetentionMs: number,
  maxQueries: number,
) {
  return [...queries]
    .filter((query) => {
      const configured = query.meta?.retentionMs;
      const retentionMs =
        typeof configured === "number" ? configured : defaultRetentionMs;
      return now - query.state.dataUpdatedAt <= retentionMs;
    })
    .sort((left, right) => right.state.dataUpdatedAt - left.state.dataUpdatedAt)
    .slice(0, maxQueries);
}

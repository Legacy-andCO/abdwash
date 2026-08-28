const UUID_SEGMENT =
  /\/[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}(?=\/|$)/gi;

export function apiRouteTemplate(path: string) {
  return path.split("?", 1)[0].replace(UUID_SEGMENT, "/:id");
}

export function apiDurationMs(startedAt: number, finishedAt = Date.now()) {
  return Math.max(0, finishedAt - startedAt);
}

import type { Job } from "../lib";
import { ClientEventIdStore } from "../idempotency/clientEventId";

export type JobAction = "start-trip" | "arrive" | "start" | "complete";

type JobActionMutation = (variables: {
  jobId: string;
  action: JobAction;
  body: object;
}) => Promise<Job>;

export class JobActionPreflightError extends Error {
  constructor(
    public readonly phase: "client_event_id",
    options?: ErrorOptions,
  ) {
    super("The app could not prepare the job action.", options);
    this.name = "JobActionPreflightError";
  }
}

export async function submitJobAction(
  mutate: JobActionMutation,
  eventIds: ClientEventIdStore,
  jobId: string,
  action: JobAction,
  extra: object = {},
  reportPreflightFailure?: (error: unknown, phase: "client_event_id") => void,
): Promise<Job> {
  const key = `${jobId}:${action}`;
  let clientEventId: string;
  try {
    clientEventId = eventIds.get(key);
  } catch (error) {
    reportPreflightFailure?.(error, "client_event_id");
    throw new JobActionPreflightError("client_event_id", { cause: error });
  }
  try {
    const result = await mutate({
      jobId,
      action,
      body: {
        client_event_id: clientEventId,
        client_timestamp: new Date().toISOString(),
        ...extra,
      },
    });
    eventIds.succeeded(key);
    return result;
  } catch (error) {
    eventIds.failed(key, error);
    throw error;
  }
}

import { ApiError } from "../errors/domainErrors";
import {
  acquireTripOrigin,
  type TripLocationFailure,
  type TripLocationSource,
  type TripOrigin,
} from "./startTripLocation";
import {
  reportTripDiagnostic,
  type TripDiagnosticReporter,
} from "./tripDiagnostics";

export type TripFlowStage = "idle" | "getting_location" | "starting_trip";

export async function runStartTripFlow<T>({
  source,
  submit,
  confirmFallback,
  onStage,
  report = reportTripDiagnostic,
}: {
  source: TripLocationSource;
  submit: (origin: TripOrigin | null) => Promise<T>;
  confirmFallback: (failure: TripLocationFailure) => Promise<boolean>;
  onStage: (stage: TripFlowStage) => void;
  report?: TripDiagnosticReporter;
}): Promise<T | null> {
  report("trip_button_pressed");
  report("trip_location_started");
  onStage("getting_location");
  const result = await acquireTripOrigin(source, 9_000, Date.now(), report);
  let origin: TripOrigin | null;
  if ("failure" in result) {
    if (!(await confirmFallback(result.failure))) {
      onStage("idle");
      return null;
    }
    report("trip_fallback_selected");
    origin = null;
  } else {
    origin = result.origin;
  }
  onStage("starting_trip");
  report("trip_api_started");
  try {
    const updated = await submit(origin);
    report("trip_api_success");
    return updated;
  } catch (error) {
    report(
      "trip_api_failed",
      error instanceof ApiError
        ? {
            endpoint: error.endpoint,
            status: error.status,
            code: error.code,
            request_id: error.requestId,
          }
        : { code: "UNKNOWN_ERROR" },
    );
    throw error;
  } finally {
    onStage("idle");
  }
}

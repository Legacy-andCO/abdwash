export type TripDiagnosticPhase =
  | "trip_button_pressed"
  | "trip_location_started"
  | "trip_location_last_known"
  | "trip_location_current_started"
  | "trip_location_success"
  | "trip_location_failed"
  | "trip_fallback_selected"
  | "trip_api_started"
  | "trip_api_success"
  | "trip_api_failed";

export type TripDiagnosticMetadata = {
  endpoint?: string;
  status?: number;
  code?: string;
  request_id?: string;
  source?: "last_known" | "current";
  usable?: boolean;
};

export type TripDiagnosticReporter = (
  phase: TripDiagnosticPhase,
  metadata?: TripDiagnosticMetadata,
) => void;

export const reportTripDiagnostic: TripDiagnosticReporter = (
  phase,
  metadata = {},
) => {
  // Deliberately excludes coordinates, request bodies, tokens and customer data.
  console.info(`[AbdWash Trip] ${phase}`, metadata);
};

export function reportTripApiPreflightFailure(
  error: unknown,
  phase: "client_event_id",
): void {
  if (!__DEV__) return;
  console.error("[AbdWash Trip] trip_api_preflight_failed", {
    error_type: error instanceof Error ? error.name : typeof error,
    phase,
  });
}

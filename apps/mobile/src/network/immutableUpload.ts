// An uncertain previous upload may already have created this server-assigned path.
// Finalization still authorizes the object and validates its bytes on the backend.
export function alreadyUploaded(error: unknown): boolean {
  return typeof error === "object" && error !== null &&
    "statusCode" in error && Number(error.statusCode) === 409;
}

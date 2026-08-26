export class ApiError extends Error {
  constructor(
    public readonly code: string,
    public readonly status: number,
    message?: string,
    public readonly requestId?: string,
    public readonly endpoint?: string,
  ) {
    super(message ?? code);
    this.name = "ApiError";
  }
}

const messages: Record<string, string> = {
  OFFLINE: "Unable to reach Trifecta. Check your connection and try again.",
  REQUEST_TIMEOUT: "The request took too long. Please try again.",
  UNAUTHORIZED: "Your session expired. Please sign in again.",
  STAFF_ACCESS_REQUIRED: "This account does not have staff access.",
  TEAM_ASSIGNMENT_CONFLICT:
    "This team already has another job during this appointment.",
  SHIFT_ASSIGNMENT_CONFLICT: "This employee already has a shift on this date.",
  SHIFT_NAME_TAKEN: "A shift with this name already exists.",
  STAFF_NOT_ON_TEAM:
    "Add this employee to that team before assigning the shift.",
  LEAVE_HAS_ASSIGNED_WORK:
    "This employee still has work assigned during the requested leave.",
  HOLD_CONFLICT:
    "That appointment was just taken. Choose another available time.",
  HOLD_EXPIRED: "That appointment hold expired. Choose the time again.",
  NO_AVAILABILITY: "No available appointments for this date.",
  USERNAME_TAKEN: "This username is already in use.",
  INVALID_STAFF_USERNAME:
    "Use 3–32 lowercase letters, numbers, dots, underscores or hyphens.",
  INVALID_PHONE: "Enter a valid international phone number.",
  STAFF_AUTH_UNAVAILABLE:
    "Staff account management is temporarily unavailable.",
  STAFF_AUTH_CREATE_FAILED:
    "The staff login could not be created. Please try again.",
  STAFF_AUTH_UPDATE_FAILED:
    "The staff login could not be updated. Please try again.",
  ACTIVE_RESCHEDULE_CONFIRMATION_REQUIRED:
    "Confirm that the active job should be reset before rescheduling.",
};

export function domainErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (messages[error.code]) return messages[error.code];
    if (error.status >= 500 || error.code === "REQUEST_FAILED") return fallback;
    return error.message || fallback;
  }
  if (error instanceof Error && messages[error.message])
    return messages[error.message];
  return fallback;
}

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
  RESCHEDULE_UNCONFIRMED:
    "We couldn't confirm the reschedule. Try again safely.",
  UNAUTHORIZED: "Your session expired. Please sign in again.",
  STAFF_ACCESS_REQUIRED: "This account does not have staff access.",
  TEAM_ASSIGNMENT_CONFLICT:
    "This team already has another job during this appointment.",
  TEAM_TIME_CONFLICT: "This team has a conflicting job during this appointment.",
  TEAM_TURNAROUND_CONFLICT:
    "This team needs more turnaround time. Confirm the override to continue.",
  TEAM_NOT_AVAILABLE: "This team is not operationally available.",
  NO_TEAM_CAPACITY: "No team is available for this appointment.",
  BOOKING_ASSIGNMENT_CHANGED:
    "The existing manual assignment cannot keep this time. Review the assignment.",
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
  SERVICE_CHECKLIST_INCOMPLETE:
    "Complete all required service checklist items before finishing the job.",
  JOB_PHOTO_STORAGE_UNAVAILABLE:
    "Photo storage is temporarily unavailable. Keep the preview and try again.",
  JOB_PHOTO_UPLOAD_GRANT_FAILED:
    "The photo upload could not be authorized. Keep the preview and try again.",
  JOB_PHOTO_UPLOAD_NOT_FOUND:
    "The uploaded photo could not be confirmed. Keep the preview and try again.",
  INVALID_JOB_PHOTO:
    "That photo could not be confirmed. Choose it again and retry.",
  CHECKLIST_NOT_AVAILABLE:
    "Start the wash before updating its service checklist.",
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

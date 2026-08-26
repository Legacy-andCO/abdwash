export const MIN_STAFF_PASSWORD_LENGTH = 8;

export function validatePasswordConfirmation(
  password: string,
  confirmation: string,
): string | null {
  if (password.length < MIN_STAFF_PASSWORD_LENGTH) {
    return `Password must be at least ${MIN_STAFF_PASSWORD_LENGTH} characters.`;
  }
  if (password !== confirmation) return "Passwords do not match.";
  return null;
}

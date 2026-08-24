const usernamePattern = /^[a-z0-9](?:[a-z0-9._-]{1,62}[a-z0-9])?$/;
const staffEmailDomain = "staff.abdwash.local";

export function normalizeStaffUsername(value: string): string {
  const username = value.trim().toLowerCase();
  if (!usernamePattern.test(username)) throw new Error("INVALID_STAFF_USERNAME");
  return username;
}

export function staffLoginEmail(value: string): string {
  const login = value.trim().toLowerCase();
  if (login.includes("@")) return login;
  return `${normalizeStaffUsername(login)}@${staffEmailDomain}`;
}

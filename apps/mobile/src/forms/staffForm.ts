import { parsePhoneNumberFromString } from "libphonenumber-js";
import type { Profile, Team } from "../lib";

const USERNAME_PATTERN = /^[a-z0-9](?:[a-z0-9._-]{1,30}[a-z0-9])?$/;

export type AddStaffValues = {
  name: string;
  username: string;
  phone: string;
  password: string;
};

export type AddStaffErrors = Partial<Record<keyof AddStaffValues, string>>;

export function normalizeStaffUsername(value: string) {
  return value.trim().toLowerCase();
}

export function normalizeStaffPhone(value: string): string | null {
  if (!value.trim()) return null;
  const phone = parsePhoneNumberFromString(value, "AE");
  return phone?.isValid() ? phone.number : null;
}

export function validateAddStaff(values: AddStaffValues): AddStaffErrors {
  const errors: AddStaffErrors = {};
  const meaningfulNameCharacters = values.name.trim().match(/[\p{L}\p{N}]/gu)?.length ?? 0;
  if (meaningfulNameCharacters < 2)
    errors.name = "Enter at least 2 meaningful characters.";

  const username = normalizeStaffUsername(values.username);
  if (username.length < 3 || username.length > 32)
    errors.username = "Username must be 3–32 characters.";
  else if (!USERNAME_PATTERN.test(username))
    errors.username =
      "Use lowercase letters, numbers, dots, underscores or hyphens; start and end with a letter or number.";

  if (values.phone.trim() && !normalizeStaffPhone(values.phone))
    errors.phone = "Enter a valid UAE or international phone number.";

  if (values.password.length < 8)
    errors.password = "Password must be at least 8 characters.";
  return errors;
}

export function eligibleTeamsForStaff(
  staffId: string,
  staff: Profile[],
  teams: Team[],
) {
  const memberships = new Set(
    staff.find((profile) => profile.id === staffId)?.teams.map((team) => team.id) ?? [],
  );
  return teams.filter((team) => team.is_active && memberships.has(team.id));
}

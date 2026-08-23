import {
  AsYouType,
  getCountries,
  getCountryCallingCode,
  parsePhoneNumberFromString,
  type CountryCode,
} from "libphonenumber-js/min";

export { getCountries, getCountryCallingCode, type CountryCode };

export function formatPhoneInput(value: string, country: CountryCode): string {
  return new AsYouType(country).input(value);
}

export function normalizePhone(value: string, country: CountryCode = "AE"): string | null {
  const phone = parsePhoneNumberFromString(value, country);
  return phone?.isValid() ? phone.number : null;
}

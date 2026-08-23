"use client";

import { useMemo } from "react";
import {
  formatPhoneInput,
  getCountries,
  getCountryCallingCode,
  type CountryCode,
} from "@/lib/phone";

type PhoneInputProps = {
  value: string;
  country: CountryCode;
  error?: string;
  onChange: (value: string) => void;
  onCountryChange: (country: CountryCode) => void;
};

export function PhoneInput({
  value,
  country,
  error,
  onChange,
  onCountryChange,
}: PhoneInputProps) {
  const countries = useMemo(() => {
    const names = new Intl.DisplayNames(["en"], { type: "region" });
    return getCountries()
      .map((code) => ({ code, name: names.of(code) ?? code }))
      .sort((left, right) => left.name.localeCompare(right.name));
  }, []);

  return (
    <label className="phone-field">
      <span>Phone number (WhatsApp number)</span>
      <span className="phone-control">
        <select
          aria-label="Phone country"
          value={country}
          onChange={(event) => {
            const nextCountry = event.target.value as CountryCode;
            onCountryChange(nextCountry);
            onChange(`+${getCountryCallingCode(nextCountry)} `);
          }}
        >
          {countries.map(({ code, name }) => (
            <option key={code} value={code}>
              {name} (+{getCountryCallingCode(code)})
            </option>
          ))}
        </select>
        <input
          type="tel"
          autoComplete="tel"
          inputMode="tel"
          placeholder="050 123 4567"
          value={value}
          aria-invalid={!!error}
          aria-describedby={error ? "phone-error" : "phone-hint"}
          onChange={(event) => onChange(formatPhoneInput(event.target.value, country))}
        />
      </span>
      <small id="phone-hint" className="field-hint">
        UAE is selected by default. International numbers are welcome.
      </small>
      {error && <span className="field-error" id="phone-error" role="alert">{error}</span>}
    </label>
  );
}

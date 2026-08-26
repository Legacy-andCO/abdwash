"use client";

import { useMemo } from "react";
import {
  formatPhoneInput,
  getCountries,
  getCountryCallingCode,
  type CountryCode,
} from "@/lib/phone";
import { useI18n } from "./i18n-provider";

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
  const { locale, t } = useI18n();
  const countries = useMemo(() => {
    const names = new Intl.DisplayNames([locale], { type: "region" });
    return getCountries()
      .map((code) => ({ code, name: names.of(code) ?? code }))
      .sort((left, right) => left.name.localeCompare(right.name));
  }, [locale]);

  return (
    <label className="phone-field">
      <span>{t("phone.number")}</span>
      <span className="phone-control">
        <select
          aria-label={t("phone.country")}
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
          placeholder={t("phone.placeholder")}
          value={value}
          aria-invalid={!!error}
          aria-describedby={error ? "phone-error" : "phone-hint"}
          onChange={(event) => onChange(formatPhoneInput(event.target.value, country))}
        />
      </span>
      <small id="phone-hint" className="field-hint">
        {t("phone.hint")}
      </small>
      {error && <span className="field-error" id="phone-error" role="alert">{error}</span>}
    </label>
  );
}

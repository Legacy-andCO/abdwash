"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { usePathname } from "next/navigation";
import type { CountryCode } from "libphonenumber-js/min";
import { createCustomerVehicle, updateCustomerProfile } from "@/lib/api";
import {
  loadCustomerProfile,
  setCachedCustomerProfile,
} from "@/lib/customer-profile-resource";
import { normalizePhone } from "@/lib/phone";
import type { CustomerProfileBootstrap } from "@/lib/types";
import { VEHICLE_TYPES } from "@/lib/vehicle-types";
import { useAuth } from "./auth-provider";
import { useI18n } from "./i18n-provider";
import { PhoneInput } from "./phone-input";

type Step = "idle" | "core" | "vehicle" | "done";

export function profileNeedsOnboarding(data: CustomerProfileBootstrap): boolean {
  return !(
    data.profile?.first_name.trim() &&
    data.profile.surname.trim() &&
    data.profile.phone.trim()
  );
}

export function CustomerOnboarding() {
  const {
    user,
    loading: authLoading,
    recoveryMode,
    dismissProfileOnboarding,
  } = useAuth();
  const { t } = useI18n();
  const pathname = usePathname();
  const dialogRef = useRef<HTMLDivElement>(null);
  const loadedUserId = useRef<string | null>(null);
  const [step, setStep] = useState<Step>("idle");
  const [data, setData] = useState<CustomerProfileBootstrap | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [country, setCountry] = useState<CountryCode>("AE");
  const [core, setCore] = useState({ first_name: "", surname: "", phone: "" });
  const [vehicle, setVehicle] = useState({
    make: "",
    model: "",
    year: "",
    vehicle_type: "",
    plate_number: "",
  });

  const excluded =
    pathname === "/auth/confirm" || pathname === "/auth/reset-password";
  const userId = user?.id ?? null;
  const metadataFirstName = String(user?.user_metadata.first_name ?? "");
  const metadataSurname = String(user?.user_metadata.surname ?? "");
  const onboardingDismissed =
    user?.user_metadata.profile_onboarding_dismissed === true;

  const load = useCallback(async () => {
    if (!userId || recoveryMode || excluded) return;
    const dismissalKey = `trifecta-profile-onboarding-dismissed:${userId}`;
    if (
      window.localStorage.getItem(dismissalKey) === "1" ||
      onboardingDismissed
    ) {
      setStep("done");
      return;
    }
    setError("");
    try {
      const next = await loadCustomerProfile(userId);
      setData(next);
      if (!profileNeedsOnboarding(next)) {
        setStep("done");
        return;
      }
      setCore({
        first_name: next.profile?.first_name ?? metadataFirstName,
        surname: next.profile?.surname ?? metadataSurname,
        phone: next.profile?.phone ?? "",
      });
      setStep("core");
    } catch {
      // Profile checks are a convenience and must never cover the website on failure.
      setStep("done");
    }
  }, [
    excluded,
    metadataFirstName,
    metadataSurname,
    onboardingDismissed,
    recoveryMode,
    userId,
  ]);

  useEffect(() => {
    if (authLoading || !userId || recoveryMode || excluded) {
      return;
    }
    if (loadedUserId.current === userId) return;
    loadedUserId.current = userId;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [authLoading, excluded, load, recoveryMode, userId]);

  useEffect(() => {
    if (!userId) {
      loadedUserId.current = null;
    }
  }, [userId]);

  useEffect(() => {
    if (!["core", "vehicle"].includes(step)) return;
    dialogRef.current?.querySelector<HTMLElement>("input, select, button")?.focus();
  }, [step]);

  function trapFocus(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Tab") return;
    const elements = Array.from(
      dialogRef.current?.querySelectorAll<HTMLElement>(
        "button:not([disabled]), input:not([disabled]), select:not([disabled])",
      ) ?? [],
    );
    if (!elements.length) return;
    const first = elements[0];
    const last = elements[elements.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  async function saveCore() {
    if (!user) return;
    const phone = normalizePhone(core.phone, country);
    if (!core.first_name.trim() || !core.surname.trim() || !phone) {
      setError(t("onboarding.required"));
      return;
    }
    setSaving(true);
    setError("");
    try {
      const next = await updateCustomerProfile({
        first_name: core.first_name.trim(),
        surname: core.surname.trim(),
        phone,
      });
      setCachedCustomerProfile(user.id, next);
      setData(next);
      setStep("vehicle");
    } catch {
      setError(t("onboarding.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  async function saveVehicle() {
    if (!user) return;
    if (
      !vehicle.make.trim() ||
      !vehicle.model.trim() ||
      !vehicle.vehicle_type ||
      !vehicle.plate_number.trim()
    ) {
      setError(t("onboarding.required"));
      return;
    }
    setSaving(true);
    setError("");
    try {
      const created = await createCustomerVehicle({
        make: vehicle.make.trim(),
        model: vehicle.model.trim(),
        year: vehicle.year ? Number(vehicle.year) : null,
        vehicle_type: vehicle.vehicle_type,
        colour: null,
        plate_number: vehicle.plate_number.trim(),
        notes: null,
      });
      if (data) {
        const next = { ...data, vehicles: [...data.vehicles, created] };
        setCachedCustomerProfile(user.id, next);
      }
      setStep("done");
    } catch {
      setError(t("onboarding.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  function skipOnboarding() {
    if (!userId) return;
    setStep("done");
    window.localStorage.setItem(
      `trifecta-profile-onboarding-dismissed:${userId}`,
      "1",
    );
    void dismissProfileOnboarding().catch(() => undefined);
  }

  if (
    step === "idle" ||
    step === "done" ||
    !user ||
    recoveryMode ||
    excluded
  ) return null;

  return (
    <div className="onboarding-backdrop">
      <div
        ref={dialogRef}
        className="onboarding-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-title"
        onKeyDown={trapFocus}
      >
        {step === "core" && (
          <>
            <p className="eyebrow"><span /> {t("onboarding.eyebrow")}</p>
            <h2 id="onboarding-title">{t("onboarding.title")}</h2>
            <p>{t("onboarding.copy")}</p>
            <div className="form-grid two onboarding-form">
              <label>
                <span>{t("booking.details.firstName")}</span>
                <input value={core.first_name} onChange={(event) => setCore({ ...core, first_name: event.target.value })} />
              </label>
              <label>
                <span>{t("booking.details.surname")}</span>
                <input value={core.surname} onChange={(event) => setCore({ ...core, surname: event.target.value })} />
              </label>
              <label>
                <span>{t("auth.email")}</span>
                <input className="bidi-ltr" value={data?.authenticated_email ?? user.email ?? ""} readOnly aria-readonly="true" />
                <small>{t("onboarding.verifiedEmail")}</small>
              </label>
              <PhoneInput
                value={core.phone}
                country={country}
                onChange={(phone) => setCore({ ...core, phone })}
                onCountryChange={setCountry}
              />
            </div>
            {error && <div className="error-banner" role="alert">{error}</div>}
            <div className="onboarding-actions">
              <button className="button" type="button" disabled={saving} onClick={() => void saveCore()}>
                {saving ? t("common.saving") : t("onboarding.continue")}
              </button>
              <button className="auth-switch" type="button" disabled={saving} onClick={skipOnboarding}>{t("onboarding.skip")}</button>
            </div>
          </>
        )}
        {step === "vehicle" && (
          <>
            <p className="eyebrow"><span /> {t("onboarding.eyebrow")}</p>
            <h2 id="onboarding-title">{t("onboarding.vehicleTitle")}</h2>
            <p>{t("onboarding.vehicleCopy")}</p>
            <div className="form-grid two onboarding-form">
              <label><span>{t("onboarding.vehicleMake")}</span><input value={vehicle.make} onChange={(event) => setVehicle({ ...vehicle, make: event.target.value })} /></label>
              <label><span>{t("onboarding.vehicleModel")}</span><input value={vehicle.model} onChange={(event) => setVehicle({ ...vehicle, model: event.target.value })} /></label>
              <label><span>{t("onboarding.vehicleYear")} <em>{t("common.optional")}</em></span><input inputMode="numeric" value={vehicle.year} onChange={(event) => setVehicle({ ...vehicle, year: event.target.value })} /></label>
              <label>
                <span>{t("onboarding.vehicleType")}</span>
                <select value={vehicle.vehicle_type} onChange={(event) => setVehicle({ ...vehicle, vehicle_type: event.target.value })}>
                  <option value="">{t("booking.vehicles.selectType")}</option>
                  {VEHICLE_TYPES.map((type) => <option key={type} value={type}>{t(`booking.vehicles.type.${type}`)}</option>)}
                </select>
              </label>
              <label><span>{t("onboarding.vehiclePlate")}</span><input className="bidi-ltr" value={vehicle.plate_number} onChange={(event) => setVehicle({ ...vehicle, plate_number: event.target.value })} /></label>
            </div>
            {error && <div className="error-banner" role="alert">{error}</div>}
            <div className="onboarding-actions">
              <button className="button" type="button" disabled={saving} onClick={() => void saveVehicle()}>{saving ? t("common.saving") : t("onboarding.addVehicle")}</button>
              <button className="button button-ghost" type="button" disabled={saving} onClick={skipOnboarding}>{t("onboarding.later")}</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { BrandMark } from "./brand-mark";
import { LocationPicker } from "./location-picker";
import { PhoneInput } from "./phone-input";
import { useAuth } from "./auth-provider";
import { LanguageSwitcher, useI18n } from "./i18n-provider";
import { ApiError, createBooking, createHold, getAvailability, getCatalogue, getCustomerProfile } from "@/lib/api";
import { localizedCustomerError } from "@/lib/customer-error";
import { bookingReducer, contactErrors, initialBookingState, steps, vehicleErrors, type BookingStep } from "@/lib/booking-state";
import { calendarCells, dateKey, formatMoney, formatSchedule, todayInTimezone } from "@/lib/dates";
import { normalizePhone } from "@/lib/phone";
import type { AvailabilitySlot, Service, Vehicle } from "@/lib/types";
import { localizePaymentStatus, localizeServiceDescription, localizeServiceName } from "@/lib/i18n";

const vehicleTypes = ["sedan", "suv", "hatchback", "coupe", "pickup", "van", "other"] as const;

function FieldError({ id, children }: { id: string; children?: string }) {
  if (!children) return null;
  return (
    <span className="field-error" id={id} role="alert">
      {children}
    </span>
  );
}

function WizardProgress({ step }: { step: BookingStep }) {
  const { t } = useI18n();
  const stepLabels: Record<BookingStep, string> = { service: t("booking.steps.service"), details: t("booking.steps.details"), vehicles: t("booking.steps.vehicles"), review: t("booking.steps.review"), schedule: t("booking.steps.schedule"), payment: t("booking.steps.payment"), confirmation: t("booking.steps.confirmation") };
  const active = steps.indexOf(step);
  return (
    <div className="wizard-progress">
      <p>{t("booking.progressStep", { current: Math.min(active + 1, 6), total: 6 })}</p>
      <div className="progress-track" aria-hidden="true">
        <span style={{ width: `${Math.min(((active + 1) / 6) * 100, 100)}%` }} />
      </div>
      <ol>
        {steps.slice(0, 6).map((item, index) => (
          <li className={index === active ? "active" : index < active ? "complete" : ""} key={item}>
            <span>{index < active ? "✓" : index + 1}</span>
            {stepLabels[item]}
          </li>
        ))}
      </ol>
    </div>
  );
}

function BookingHeader() {
  const { t } = useI18n();
  return (
    <header className="booking-header">
      <div className="shell">
        <Link className="brand" href="/" aria-label={t("brand.home")}><BrandMark /></Link>
        <LanguageSwitcher compact />
        <Link className="quiet-link" href="/">
          {t("booking.saveExit")} <span aria-hidden="true">×</span>
        </Link>
      </div>
    </header>
  );
}

export function BookingWizard({ initialServiceId }: { initialServiceId: string }) {
  const { language, t } = useI18n();
  const translationRef = useRef(t);
  const [state, dispatch] = useReducer(bookingReducer, initialBookingState);
  const [loading, setLoading] = useState(true);
  const [catalogueError, setCatalogueError] = useState<unknown>(null);
  const [profileWarning, setProfileWarning] = useState("");
  const { user, loading: authLoading } = useAuth();
  useEffect(() => { translationRef.current = t; }, [t]);
  const loadCatalogue = () => {
    setLoading(true);
    setCatalogueError(null);
    getCatalogue()
      .then((catalogue) => {
        dispatch({ type: "catalogue", value: catalogue });
        if (initialServiceId && catalogue.services.some((service) => service.id === initialServiceId)) dispatch({ type: "service", value: initialServiceId });
      })
      .catch(setCatalogueError)
      .finally(() => setLoading(false));
  };
  useEffect(() => {
    if (authLoading) return;
    let active = true;
    void Promise.allSettled([getCatalogue(), user ? getCustomerProfile() : Promise.resolve(null)]).then(([catalogueResult, profileResult]) => {
      if (!active) return;
      if (catalogueResult.status === "rejected") setCatalogueError(catalogueResult.reason);
      else {
        dispatch({ type: "catalogue", value: catalogueResult.value });
        if (initialServiceId && catalogueResult.value.services.some((service) => service.id === initialServiceId)) dispatch({ type: "service", value: initialServiceId });
      }
      if (profileResult.status === "fulfilled" && profileResult.value) dispatch({ type: "customer_bootstrap", value: profileResult.value });
      else if (profileResult.status === "rejected") setProfileWarning(translationRef.current("booking.profileWarning"));
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [authLoading, initialServiceId, user]);

  if (state.step === "confirmation" && state.booking && state.catalogue)
    return (
      <>
        <BookingHeader />
        <Confirmation state={state} />
      </>
    );
  return (
    <>
      <BookingHeader />
      <main className="booking-page">
        <div className="shell booking-layout">
          <aside>
            <WizardProgress step={state.step} />
            <div className="booking-aside-note">
              <span>{t("booking.help")}</span>
              <p>{t("booking.helpCopy")}</p>
            </div>
          </aside>
          <section className="wizard-card" aria-live="polite">
            {profileWarning && (
              <div className="inline-notice warning">
                <span>{profileWarning}</span>
              </div>
            )}
            {loading ? <LoadingPanel /> : catalogueError != null ? <ErrorPanel message={localizedCustomerError(catalogueError, language, t)} onRetry={loadCatalogue} /> : state.catalogue ? <WizardStep state={state} dispatch={dispatch} /> : null}
          </section>
        </div>
      </main>
    </>
  );
}

type StepProps = {
  state: typeof initialBookingState;
  dispatch: React.Dispatch<Parameters<typeof bookingReducer>[1]>;
};

function WizardStep(props: StepProps) {
  switch (props.state.step) {
    case "service":
      return <ServiceStep {...props} />;
    case "details":
      return <DetailsStep {...props} />;
    case "vehicles":
      return <VehiclesStep {...props} />;
    case "review":
      return <ReviewStep {...props} />;
    case "schedule":
      return <ScheduleStep {...props} />;
    case "payment":
      return <PaymentStep {...props} />;
    default:
      return null;
  }
}

function StepIntro({ eyebrow, title, copy }: { eyebrow: string; title: string; copy: string }) {
  return (
    <div className="step-intro">
      <p className="eyebrow">
        <span /> {eyebrow}
      </p>
      <h1>{title}</h1>
      <p>{copy}</p>
    </div>
  );
}
function StepActions({ back, next, nextLabel, busy = false, disabled = false }: { back?: () => void; next: () => void; nextLabel?: string; busy?: boolean; disabled?: boolean }) {
  const { t } = useI18n();
  return (
    <div className="step-actions">
      {back && (
        <button className="button button-ghost" type="button" onClick={back}>
          <span className="directional-icon" aria-hidden="true">←</span> {t("common.back")}
        </button>
      )}
      <button className="button" type="button" onClick={next} disabled={disabled || busy}>
        {busy ? (
          <>
            <span className="spinner" /> {t("booking.pleaseWait")}
          </>
        ) : (
          <>
            {nextLabel ?? t("common.continue")} <span className="directional-icon" aria-hidden="true">→</span>
          </>
        )}
      </button>
    </div>
  );
}

function ServiceStep({ state, dispatch }: StepProps) {
  const { language, locale, t } = useI18n();
  const services = state.catalogue!.services;
  return (
    <>
      <StepIntro eyebrow={t("booking.service.eyebrow")} title={t("booking.service.title")} copy={t("booking.service.copy")} />
      <div className="choice-list">
        {services.map((service) => (
          <label className={state.defaultServiceId === service.id ? "choice-card selected" : "choice-card"} key={service.id}>
            <input type="radio" name="service" value={service.id} checked={state.defaultServiceId === service.id} onChange={() => dispatch({ type: "service", value: service.id })} />
            <span className="choice-check" />
            <span className="choice-content">
              <strong>{localizeServiceName(language, service.name)}</strong>
              <small>{localizeServiceDescription(language, service.description, "booking.service.defaultDescription")}</small>
              <em>≈ {t("services.minutes", { minutes: service.estimated_duration_minutes })}</em>
            </span>
            <b>{formatMoney(service.price_minor, service.currency_code, locale)}</b>
          </label>
        ))}
      </div>
      <StepActions next={() => dispatch({ type: "step", value: "details" })} disabled={!state.defaultServiceId} />
    </>
  );
}

function DetailsStep({ state, dispatch }: StepProps) {
  const { t } = useI18n();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const next = () => {
    const found = contactErrors(state.contact, state.location, t);
    setErrors(found);
    if (!Object.keys(found).length) {
      const normalizedPhone = normalizePhone(state.contact.phone, state.contact.phone_country);
      if (normalizedPhone) dispatch({ type: "contact", field: "phone", value: normalizedPhone });
      dispatch({ type: "step", value: "vehicles" });
    } else {
      setTimeout(() => document.querySelector<HTMLElement>("[aria-invalid=true]")?.focus(), 0);
    }
  };
  const contactField = (field: "first_name" | "surname" | "email", label: string, type = "text", autocomplete?: string) => (
    <label>
      <span>{label}</span>
      <input type={type} autoComplete={autocomplete} value={state.contact[field]} aria-invalid={!!errors[field]} aria-describedby={errors[field] ? `${field}-error` : undefined} onChange={(event) => dispatch({ type: "contact", field, value: event.target.value })} />
      <FieldError id={`${field}-error`}>{errors[field]}</FieldError>
    </label>
  );
  const updateLocationField = useCallback(
    (field: "written_address" | "location_url" | "instructions", value: string) => {
      if (field === "location_url") dispatch({ type: "manual_location_url", value });
      else dispatch({ type: "location", field, value });
    },
    [dispatch],
  );
  const updateCoordinates = useCallback(
    (value: { latitude: number; longitude: number }, writtenAddress?: string) => {
      dispatch({ type: "location_coordinates", value, writtenAddress });
    },
    [dispatch],
  );

  const savedLocations = state.customerProfile?.addresses ?? [];

  return (
    <>
      <StepIntro eyebrow={t("booking.details.eyebrow")} title={t("booking.details.title")} copy={t("booking.details.copy")} />
      {savedLocations.length > 0 && (
        <div className="form-section">
          <h2>{t("booking.details.savedLocation")}</h2>
          <div className="choice-list compact">
            {savedLocations.map((address) => (
              <button className="choice-card" type="button" key={address.id} onClick={() => dispatch({ type: "saved_location", value: address })}>
                <span className="choice-content">
                  <strong>
                    {address.label}
                    {address.is_default ? ` · ${t("booking.details.default")}` : ""}
                  </strong>
                  <small>{address.written_address}</small>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="form-section">
        <h2>{t("booking.details.contact")}</h2>
        <div className="form-grid two">
          {contactField("first_name", t("booking.details.firstName"), "text", "given-name")}
          {contactField("surname", t("booking.details.surname"), "text", "family-name")}
          {contactField("email", t("booking.details.email"), "email", "email")}
          <PhoneInput value={state.contact.phone} country={state.contact.phone_country} error={errors.phone} onChange={(value) => dispatch({ type: "contact", field: "phone", value })} onCountryChange={(value) => dispatch({ type: "contact", field: "phone_country", value })} />
        </div>
      </div>
      <div className="form-section">
        <h2>{t("booking.details.serviceLocation")}</h2>
        <LocationPicker location={state.location} errors={errors} onFieldChange={updateLocationField} onCoordinatesChange={updateCoordinates} />
      </div>
      <StepActions back={() => dispatch({ type: "step", value: "service" })} next={next} />
    </>
  );
}

function VehiclesStep({ state, dispatch }: StepProps) {
  const { t } = useI18n();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const next = () => {
    const found = vehicleErrors(state.vehicles, t);
    setErrors(found);
    if (!Object.keys(found).length) dispatch({ type: "step", value: "review" });
    else setTimeout(() => document.querySelector<HTMLElement>("[aria-invalid=true]")?.focus(), 0);
  };
  return (
    <>
      <StepIntro eyebrow={t("booking.vehicles.eyebrow")} title={state.vehicles.length === 1 ? t("booking.vehicles.titleOne") : t("booking.vehicles.titleMany", { count: state.vehicles.length })} copy={t("booking.vehicles.copy")} />
      {(state.customerProfile?.vehicles.length ?? 0) > 0 && (
        <div className="form-section">
          <h2>{t("booking.vehicles.saved")}</h2>
          <div className="choice-list compact">
            {state.customerProfile!.vehicles.map((vehicle) => (
              <button className="choice-card" type="button" key={vehicle.id} onClick={() => dispatch({ type: "saved_vehicle", value: vehicle })}>
                <span className="choice-content">
                  <strong>
                    {vehicle.make} {vehicle.model}
                  </strong>
                  <small className="bidi-ltr">{vehicle.plate_number ? t("booking.vehicles.plate", { plate: vehicle.plate_number }) : t("booking.vehicles.savedVehicle")}</small>
                </span>
                <b>{t("booking.vehicles.use")}</b>
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="vehicle-stack">
        {state.vehicles.map((vehicle, index) => (
          <VehicleCard key={vehicle.key} vehicle={vehicle} index={index} services={state.catalogue!.services} errors={errors} canRemove={state.vehicles.length > 1} dispatch={dispatch} />
        ))}
      </div>
      <button className="add-button" type="button" onClick={() => dispatch({ type: "add_vehicle" })}>
        <span>+</span> {t("booking.vehicles.add")}
      </button>
      {state.vehicles.length >= state.catalogue!.settings.multi_vehicle_threshold && (
        <div className="inline-notice">
          <strong>{t("booking.vehicles.timeTitle")}</strong>
          <span>{t("booking.vehicles.timeCopy")}</span>
        </div>
      )}
      <StepActions back={() => dispatch({ type: "step", value: "details" })} next={next} />
    </>
  );
}

function VehicleCard({ vehicle, index, services, errors, canRemove, dispatch }: { vehicle: Vehicle; index: number; services: Service[]; errors: Record<string, string>; canRemove: boolean; dispatch: StepProps["dispatch"] }) {
  const { language, locale, t } = useI18n();
  const update = (field: keyof Vehicle, value: string) => dispatch({ type: "vehicle", key: vehicle.key, field, value });
  const input = (field: keyof Vehicle, label: string, placeholder = "") => (
    <label>
      <span>{label}</span>
      <input required={field === "plate_number"} value={vehicle[field]} placeholder={placeholder} aria-invalid={!!errors[`${vehicle.key}.${field}`]} aria-describedby={errors[`${vehicle.key}.${field}`] ? `${vehicle.key}-${field}-error` : undefined} onChange={(event) => update(field, event.target.value)} />
      <FieldError id={`${vehicle.key}-${field}-error`}>{errors[`${vehicle.key}.${field}`]}</FieldError>
    </label>
  );
  return (
    <fieldset className="vehicle-card">
      <legend>
        <span>{t("common.vehicle")} {index + 1}</span>
        {canRemove && (
          <button type="button" onClick={() => dispatch({ type: "remove_vehicle", key: vehicle.key })}>
            {t("common.remove")}
          </button>
        )}
      </legend>
      <div className="form-grid two">
        {input("make", t("booking.vehicles.make"), "Toyota")}
        {input("model", t("booking.vehicles.model"), "Camry")}
        {input("year", t("booking.vehicles.year"), "2024")}
        <label>
          <span>{t("booking.vehicles.type")}</span>
          <select value={vehicle.vehicle_type} aria-invalid={!!errors[`${vehicle.key}.vehicle_type`]} onChange={(event) => update("vehicle_type", event.target.value)}>
            <option value="">{t("booking.vehicles.selectType")}</option>
            {vehicleTypes.map((type) => (
              <option key={type} value={type}>
                {t(`booking.vehicles.type.${type}`)}
              </option>
            ))}
          </select>
          <FieldError id={`${vehicle.key}-vehicle_type-error`}>{errors[`${vehicle.key}.vehicle_type`]}</FieldError>
        </label>
        {input("colour", t("booking.vehicles.colour"))}
        {input("plate_number", t("booking.vehicles.plateRequired"))}
      </div>
      <label>
        <span>{t("booking.vehicles.service")}</span>
        <select value={vehicle.service_id} aria-invalid={!!errors[`${vehicle.key}.service_id`]} onChange={(event) => update("service_id", event.target.value)}>
          {services.map((service) => (
            <option key={service.id} value={service.id}>
              {localizeServiceName(language, service.name)} — {formatMoney(service.price_minor, service.currency_code, locale)}
            </option>
          ))}
        </select>
        <FieldError id={`${vehicle.key}-service_id-error`}>{errors[`${vehicle.key}.service_id`]}</FieldError>
      </label>
      <label>
        <span>
          {t("booking.vehicles.notes")} <em>{t("common.optional")}</em>
        </span>
        <textarea rows={2} value={vehicle.notes} onChange={(event) => update("notes", event.target.value)} />
      </label>
    </fieldset>
  );
}

function ReviewStep({ state, dispatch }: StepProps) {
  const { language, locale, t } = useI18n();
  const services = new Map(state.catalogue!.services.map((service) => [service.id, service]));
  const estimate = state.vehicles.reduce((total, vehicle) => total + (services.get(vehicle.service_id)?.price_minor ?? 0), 0);
  return (
    <>
      <StepIntro eyebrow={t("booking.review.eyebrow")} title={t("booking.review.title")} copy={t("booking.review.copy")} />
      <div className="review-sections">
        <ReviewBlock title={t("booking.review.contact")} action={() => dispatch({ type: "step", value: "details" })}>
          <strong>
            {state.contact.first_name} {state.contact.surname}
          </strong>
          <span>{state.contact.email}</span>
          <span>{state.contact.phone}</span>
        </ReviewBlock>
        <ReviewBlock title={t("booking.review.location")} action={() => dispatch({ type: "step", value: "details" })}>
          <strong>{state.location.written_address}</strong>
          <a href={state.location.location_url} target="_blank" rel="noreferrer">
            {t("booking.review.openMap")} ↗
          </a>
          <span>{t("booking.review.locationNotes", { notes: state.location.instructions })}</span>
        </ReviewBlock>
        <ReviewBlock title={`${t("common.vehicles")} · ${state.vehicles.length}`} action={() => dispatch({ type: "step", value: "vehicles" })}>
          {state.vehicles.map((vehicle) => (
            <div className="review-vehicle" key={vehicle.key}>
              <span>
                <strong>
                  {vehicle.make} {vehicle.model}
                </strong>
                <small>{[vehicle.year, vehicle.colour].filter(Boolean).join(" · ")}</small>
                <small className="bidi-ltr">{t("booking.vehicles.plate", { plate: vehicle.plate_number })}</small>
              </span>
              <b>{localizeServiceName(language, services.get(vehicle.service_id)?.name ?? "")}</b>
            </div>
          ))}
        </ReviewBlock>
        <div className="estimate-row">
          <span>
            <strong>{t("booking.review.estimated")}</strong>
            <small>{t("booking.review.estimatedCopy")}</small>
          </span>
          <b>{formatMoney(estimate, state.catalogue!.settings.currency_code, locale)}</b>
        </div>
      </div>
      <StepActions back={() => dispatch({ type: "step", value: "vehicles" })} next={() => dispatch({ type: "step", value: "schedule" })} nextLabel={t("booking.review.chooseTime")} />
    </>
  );
}

function ReviewBlock({ title, action, children }: { title: string; action: () => void; children: React.ReactNode }) {
  const { t } = useI18n();
  return (
    <section className="review-block">
      <header>
        <h2>{title}</h2>
        <button type="button" onClick={action}>
          {t("common.edit")}
        </button>
      </header>
      <div>{children}</div>
    </section>
  );
}

function ScheduleStep({ state, dispatch }: StepProps) {
  const { language, locale, t } = useI18n();
  const timezone = state.catalogue!.settings.timezone;
  const today = todayInTimezone(timezone);
  const [year, month] = today.split("-").map(Number);
  const [visibleMonth, setVisibleMonth] = useState({
    year,
    monthIndex: month - 1,
  });
  const [availabilityLoading, setAvailabilityLoading] = useState(false);
  const [error, setError] = useState("");
  const [holding, setHolding] = useState(false);
  const loadAvailability = async (selectedDate: string) => {
    setAvailabilityLoading(true);
    setError("");
    try {
      dispatch({
        type: "availability",
        value: await getAvailability(selectedDate, state.vehicles.length),
      });
    } catch (reason) {
      setError(localizedCustomerError(reason, language, t));
    } finally {
      setAvailabilityLoading(false);
    }
  };
  const chooseDate = (value: string) => {
    dispatch({ type: "date", value });
    void loadAvailability(value);
  };
  const proceed = async () => {
    const slot = state.availability?.slots.find((item) => item.time === state.selectedSlotTime);
    if (!slot) return;
    setHolding(true);
    setError("");
    try {
      const hold = await createHold({
        date: state.selectedDate,
        start_time: slot.time,
        vehicle_count: state.vehicles.length,
        resource_id: slot.resources[0]?.resource_id,
      });
      dispatch({ type: "hold", value: hold });
      dispatch({ type: "step", value: "payment" });
    } catch (reason) {
      setError(reason instanceof ApiError && reason.isSchedulingConflict ? t("booking.schedule.taken") : localizedCustomerError(reason, language, t));
      if (reason instanceof ApiError && reason.isSchedulingConflict) await loadAvailability(state.selectedDate);
    } finally {
      setHolding(false);
    }
  };
  const moveMonth = (delta: number) => {
    const date = new Date(Date.UTC(visibleMonth.year, visibleMonth.monthIndex + delta, 1));
    setVisibleMonth({
      year: date.getUTCFullYear(),
      monthIndex: date.getUTCMonth(),
    });
  };
  const monthLabel = new Intl.DateTimeFormat(locale, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(visibleMonth.year, visibleMonth.monthIndex, 1)));
  const currentMonthKey = `${year}-${String(month).padStart(2, "0")}`;
  const visibleMonthKey = `${visibleMonth.year}-${String(visibleMonth.monthIndex + 1).padStart(2, "0")}`;
  return (
    <>
      <StepIntro eyebrow={t("booking.schedule.eyebrow")} title={t("booking.schedule.title")} copy={t("booking.schedule.copy", { timezone: timezone.replace("_", " ") })} />
      <div className="schedule-grid">
        <div className="calendar">
          <header>
            <button className="direction-aware" type="button" aria-label={t("booking.schedule.previousMonth")} disabled={visibleMonthKey <= currentMonthKey} onClick={() => moveMonth(-1)}>
              ←
            </button>
            <h2>{monthLabel}</h2>
            <button className="direction-aware" type="button" aria-label={t("booking.schedule.nextMonth")} onClick={() => moveMonth(1)}>
              →
            </button>
          </header>
          <div className="weekday-row" aria-hidden="true">
            {Array.from({ length: 7 }, (_, day) => new Intl.DateTimeFormat(locale, { weekday: "short", timeZone: "UTC" }).format(new Date(Date.UTC(2026, 7, 23 + day)))).map((day) => (
              <span key={day}>{day}</span>
            ))}
          </div>
          <div className="calendar-grid">
            {calendarCells(visibleMonth.year, visibleMonth.monthIndex).map((day, index) =>
              day ? (
                <button
                  type="button"
                  key={day}
                  className={state.selectedDate === dateKey(visibleMonth.year, visibleMonth.monthIndex, day) ? "selected" : ""}
                  disabled={dateKey(visibleMonth.year, visibleMonth.monthIndex, day) < today}
                  aria-label={new Intl.DateTimeFormat(locale, {
                    weekday: "long",
                    day: "numeric",
                    month: "long",
                    timeZone: "UTC",
                  }).format(new Date(Date.UTC(visibleMonth.year, visibleMonth.monthIndex, day)))}
                  onClick={() => chooseDate(dateKey(visibleMonth.year, visibleMonth.monthIndex, day))}
                >
                  {day}
                </button>
              ) : (
                <span key={`empty-${index}`} />
              ),
            )}
          </div>
        </div>
        <div className="times-panel">
          <h2>{state.selectedDate ? t("booking.schedule.availableStarts") : t("booking.schedule.chooseDate")}</h2>
          {availabilityLoading && (
            <div className="slot-loading">
              <span className="spinner dark" /> {t("booking.schedule.checking")}
            </div>
          )}
          {!availabilityLoading && state.availability && (
            <>
              <div className="slot-grid">
                {state.availability.slots.map((slot) => (
                  <SlotButton key={slot.time} slot={slot} selected={state.selectedSlotTime === slot.time} timezone={timezone} locale={locale} onSelect={() => dispatch({ type: "slot", value: slot.time })} />
                ))}
              </div>
              {!state.availability.slots.some((slot) => slot.available) && <p className="empty-copy">{t("booking.schedule.noTimes")}</p>}
            </>
          )}
          {!state.selectedDate && <p className="empty-copy">{t("booking.schedule.selectDate")}</p>}
        </div>
      </div>
      {state.availability?.required_slot_count && state.availability.required_slot_count > 1 ? (
        <div className="inline-notice">
          <strong>{t("booking.schedule.consecutive")}</strong>
          <span>{t("booking.schedule.consecutiveCopy", { vehicles: state.vehicles.length, slots: state.availability.required_slot_count })}</span>
        </div>
      ) : null}
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      <StepActions back={() => dispatch({ type: "step", value: "review" })} next={proceed} nextLabel={t("booking.schedule.reserve")} busy={holding} disabled={!state.selectedSlotTime} />
    </>
  );
}

function SlotButton({ slot, selected, timezone, locale, onSelect }: { slot: AvailabilitySlot; selected: boolean; timezone: string; locale: string; onSelect: () => void }) {
  const { t } = useI18n();
  const time = new Intl.DateTimeFormat(locale, {
    timeZone: timezone,
    hour: "numeric",
    minute: "2-digit",
  });
  return (
    <button type="button" className={selected ? "slot selected" : "slot"} disabled={!slot.available} aria-pressed={selected} title={slot.available ? undefined : slot.unavailable_reason?.replaceAll("_", " ").toLowerCase()} onClick={onSelect}>
      <strong>{time.format(new Date(slot.starts_at))}</strong>
      {slot.required_slot_count > 1 && <small>{t("booking.schedule.until", { time: time.format(new Date(slot.ends_at)) })}</small>}
    </button>
  );
}

function PaymentStep({ state, dispatch }: StepProps) {
  const { language, locale, t } = useI18n();
  const [choice, setChoice] = useState<"pay_after_service" | "pay_now">("pay_after_service");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const idempotencyKey = useRef("");
  const expiresAt = state.hold?.expires_at;
  const maxHoldSeconds = state.catalogue!.settings.hold_duration_minutes * 60;
  const remainingSeconds = () => (expiresAt ? Math.min(maxHoldSeconds, Math.max(0, Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000))) : 0);
  const [seconds, setSeconds] = useState(remainingSeconds);
  useEffect(() => {
    const update = () => setSeconds(expiresAt ? Math.min(maxHoldSeconds, Math.max(0, Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000))) : 0);
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [expiresAt, maxHoldSeconds]);
  const submit = async () => {
    if (!state.hold || choice !== "pay_after_service") return;
    setSubmitting(true);
    setError("");
    idempotencyKey.current ||= crypto.randomUUID();
    try {
      dispatch({
        type: "booking",
        value: await createBooking({
          hold_token: state.hold.hold_token,
          contact: state.contact,
          location: state.location,
          vehicles: state.vehicles,
          payment_choice: "pay_after_service",
          idempotencyKey: idempotencyKey.current,
        }),
      });
    } catch (reason) {
      setError(reason instanceof ApiError && reason.code === "NETWORK_ERROR" ? t("booking.payment.network") : localizedCustomerError(reason, language, t));
      if (reason instanceof ApiError && reason.isSchedulingConflict) dispatch({ type: "step", value: "schedule" });
    } finally {
      setSubmitting(false);
    }
  };
  const estimate = state.vehicles.reduce((total, vehicle) => total + (state.catalogue!.services.find((service) => service.id === vehicle.service_id)?.price_minor ?? 0), 0);
  return (
    <>
      <StepIntro eyebrow={t("booking.payment.eyebrow")} title={t("booking.payment.title")} copy={t("booking.payment.copy")} />
      {state.hold && (
        <div className={seconds < 60 ? "hold-timer urgent" : "hold-timer"}>
          <span>{t("booking.payment.reserved")}</span>
          <strong>
            {String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(seconds % 60).padStart(2, "0")}
          </strong>
        </div>
      )}
      <div className="payment-layout">
        <div className="choice-list">
          <label className={choice === "pay_after_service" ? "choice-card selected" : "choice-card"}>
            <input type="radio" name="payment" checked={choice === "pay_after_service"} onChange={() => setChoice("pay_after_service")} />
            <span className="choice-check" />
            <span className="choice-content">
              <strong>{t("booking.payment.payAfter")}</strong>
              <small>{t("booking.payment.payAfterCopy")}</small>
              <em>{t("common.availableNow")}</em>
            </span>
          </label>
          <label className={choice === "pay_now" ? "choice-card selected" : "choice-card"}>
            <input type="radio" name="payment" checked={choice === "pay_now"} onChange={() => setChoice("pay_now")} />
            <span className="choice-check" />
            <span className="choice-content">
              <strong>{t("booking.payment.payNow")}</strong>
              <small>{t("booking.payment.payNowCopy")}</small>
              <em>{t("common.comingSoon")}</em>
            </span>
          </label>
          {choice === "pay_now" && (
            <div className="inline-notice warning" role="status">
              <strong>{t("booking.payment.unavailable")}</strong>
              <span>{t("booking.payment.unavailableCopy")}</span>
            </div>
          )}
        </div>
        <aside className="payment-summary">
          <span>{t("booking.payment.estimate")}</span>
          <strong>{formatMoney(estimate, state.catalogue!.settings.currency_code, locale)}</strong>
          <p>
            {state.vehicles.length} {state.vehicles.length === 1 ? t("common.vehicle") : t("common.vehicles")}
          </p>
          {state.hold && <small>{formatSchedule(state.hold.starts_at, state.hold.ends_at, state.catalogue!.settings.timezone, locale)}</small>}
        </aside>
      </div>
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      <StepActions back={() => dispatch({ type: "step", value: "schedule" })} next={submit} nextLabel={t("booking.payment.confirm")} busy={submitting} disabled={choice !== "pay_after_service" || seconds <= 0} />
    </>
  );
}

function Confirmation({ state }: { state: typeof initialBookingState }) {
  const { language, locale, t } = useI18n();
  const booking = state.booking!;
  return (
    <main className="confirmation-page">
      <div className="confirmation-burst" aria-hidden="true">
        ✓
      </div>
      <section className="confirmation-card">
        <p className="eyebrow">
          <span /> {t("booking.confirmation.eyebrow")}
        </p>
        <h1>{t("booking.confirmation.greeting", { name: booking.customer_first_name })}</h1>
        <p className="confirmation-lead">{t("booking.confirmation.lead")}</p>
        <div className="reference-box">
          <span>{t("booking.confirmation.reference")}</span>
          <strong>{booking.reference}</strong>
        </div>
        <div className="confirmation-grid">
          <div>
            <span>{t("common.dateTime")}</span>
            <strong>{formatSchedule(booking.scheduled_start, booking.scheduled_end, state.catalogue!.settings.timezone, locale)}</strong>
          </div>
          <div>
            <span>{t("common.payment")}</span>
            <strong>{t("booking.payment.payAfter")} · {localizePaymentStatus(language, booking.payment_status)}</strong>
          </div>
          <div>
            <span>{t("common.location")}</span>
            <strong>{booking.written_address}</strong>
            <a href={booking.location_url} target="_blank" rel="noreferrer">
              {t("booking.confirmation.openMap")} ↗
            </a>
          </div>
          <div>
            <span>{t("booking.confirmation.total")}</span>
            <strong>{formatMoney(booking.total_amount_minor, booking.currency_code, locale)}</strong>
          </div>
        </div>
        <div className="confirmed-vehicles">
          <h2>{booking.vehicles.length === 1 ? t("booking.confirmation.vehicleOne") : t("booking.confirmation.vehicleMany")}</h2>
          {booking.vehicles.map((vehicle, index) => (
            <div key={`${vehicle.make}-${vehicle.model}-${index}`}>
              <span>
                <strong>
                  {vehicle.make} {vehicle.model}
                </strong>
                <small>{[vehicle.year, vehicle.colour, vehicle.plate_number].filter(Boolean).join(" · ")}</small>
              </span>
              <b>{localizeServiceName(language, vehicle.service_name)}</b>
            </div>
          ))}
        </div>
        <div className="confirmation-actions">
          <Link className="button" href={`/manage#${booking.management_token}`}>
            {t("booking.confirmation.manage")} <span className="directional-icon" aria-hidden="true">→</span>
          </Link>
          <Link className="button button-ghost" href="/">
            {t("booking.confirmation.backHome")}
          </Link>
        </div>
        <p className="confirmation-note">{t("booking.confirmation.notification", { email: state.contact.email })}</p>
      </section>
    </main>
  );
}

function LoadingPanel() {
  const { t } = useI18n();
  return (
    <div className="loading-panel">
      <span className="spinner dark" />
      <strong>{t("booking.loading.title")}</strong>
      <p>{t("booking.loading.copy")}</p>
    </div>
  );
}
function ErrorPanel({ message, onRetry }: { message: string; onRetry: () => void }) {
  const { t } = useI18n();
  return (
    <div className="loading-panel">
      <strong>{t("booking.loading.failed")}</strong>
      <p>{message}</p>
      <button className="button" type="button" onClick={onRetry}>
        {t("common.tryAgain")}
      </button>
    </div>
  );
}

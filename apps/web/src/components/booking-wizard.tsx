"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { BrandMark } from "./brand-mark";
import { ApiError, createBooking, createHold, friendlyError, getAvailability, getCatalogue } from "@/lib/api";
import { bookingReducer, contactErrors, initialBookingState, steps, vehicleErrors, type BookingStep } from "@/lib/booking-state";
import { calendarCells, dateKey, formatMoney, formatSchedule, todayInTimezone } from "@/lib/dates";
import type { AvailabilitySlot, Service, Vehicle } from "@/lib/types";

const stepLabels: Record<BookingStep, string> = { service: "Service", details: "Your details", vehicles: "Vehicles", review: "Review", schedule: "Date & time", payment: "Payment", confirmation: "Confirmed" };
const vehicleTypes = ["Sedan", "SUV", "Hatchback", "Coupe", "Pickup", "Van", "Other"];

function FieldError({ id, children }: { id: string; children?: string }) {
  if (!children) return null;
  return <span className="field-error" id={id} role="alert">{children}</span>;
}

function WizardProgress({ step }: { step: BookingStep }) {
  const active = steps.indexOf(step);
  return <div className="wizard-progress"><p>Step {Math.min(active + 1, 6)} of 6</p><div className="progress-track" aria-hidden="true"><span style={{ width: `${Math.min(((active + 1) / 6) * 100, 100)}%` }} /></div><ol>{steps.slice(0, 6).map((item, index) => <li className={index === active ? "active" : index < active ? "complete" : ""} key={item}><span>{index < active ? "✓" : index + 1}</span>{stepLabels[item]}</li>)}</ol></div>;
}

function BookingHeader() {
  return <header className="booking-header"><div className="shell"><Link className="brand" href="/"><BrandMark /><span>AbdWash</span></Link><Link className="quiet-link" href="/">Save & exit <span aria-hidden="true">×</span></Link></div></header>;
}

export function BookingWizard({ initialServiceId }: { initialServiceId: string }) {
  const [state, dispatch] = useReducer(bookingReducer, initialBookingState);
  const [loading, setLoading] = useState(true);
  const [catalogueError, setCatalogueError] = useState("");
  const loadCatalogue = () => {
    setLoading(true); setCatalogueError("");
    getCatalogue().then((catalogue) => {
      dispatch({ type: "catalogue", value: catalogue });
      if (initialServiceId && catalogue.services.some((service) => service.id === initialServiceId)) dispatch({ type: "service", value: initialServiceId });
    }).catch((error) => setCatalogueError(friendlyError(error))).finally(() => setLoading(false));
  };
  useEffect(() => {
    let active = true;
    void getCatalogue().then((catalogue) => {
      if (!active) return;
      dispatch({ type: "catalogue", value: catalogue });
      if (initialServiceId && catalogue.services.some((service) => service.id === initialServiceId)) dispatch({ type: "service", value: initialServiceId });
    }).catch((error) => { if (active) setCatalogueError(friendlyError(error)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [initialServiceId]);

  if (state.step === "confirmation" && state.booking && state.catalogue) return <><BookingHeader /><Confirmation state={state} /></>;
  return <><BookingHeader /><main className="booking-page"><div className="shell booking-layout"><aside><WizardProgress step={state.step} /><div className="booking-aside-note"><span>Need a hand?</span><p>Your choices stay here while you move between steps.</p></div></aside><section className="wizard-card" aria-live="polite">{loading ? <LoadingPanel /> : catalogueError ? <ErrorPanel message={catalogueError} onRetry={loadCatalogue} /> : state.catalogue ? <WizardStep state={state} dispatch={dispatch} /> : null}</section></div></main></>;
}

type StepProps = { state: typeof initialBookingState; dispatch: React.Dispatch<Parameters<typeof bookingReducer>[1]> };

function WizardStep(props: StepProps) {
  switch (props.state.step) {
    case "service": return <ServiceStep {...props} />;
    case "details": return <DetailsStep {...props} />;
    case "vehicles": return <VehiclesStep {...props} />;
    case "review": return <ReviewStep {...props} />;
    case "schedule": return <ScheduleStep {...props} />;
    case "payment": return <PaymentStep {...props} />;
    default: return null;
  }
}

function StepIntro({ eyebrow, title, copy }: { eyebrow: string; title: string; copy: string }) { return <div className="step-intro"><p className="eyebrow"><span /> {eyebrow}</p><h1>{title}</h1><p>{copy}</p></div>; }
function StepActions({ back, next, nextLabel = "Continue", busy = false, disabled = false }: { back?: () => void; next: () => void; nextLabel?: string; busy?: boolean; disabled?: boolean }) { return <div className="step-actions">{back && <button className="button button-ghost" type="button" onClick={back}>← Back</button>}<button className="button" type="button" onClick={next} disabled={disabled || busy}>{busy ? <><span className="spinner" /> Please wait</> : <>{nextLabel} <span aria-hidden="true">→</span></>}</button></div>; }

function ServiceStep({ state, dispatch }: StepProps) {
  const services = state.catalogue!.services;
  return <><StepIntro eyebrow="Choose your care" title="What does your car need?" copy="Select a starting service. You can assign a different service to each vehicle later." /><div className="choice-list">{services.map((service) => <label className={state.defaultServiceId === service.id ? "choice-card selected" : "choice-card"} key={service.id}><input type="radio" name="service" value={service.id} checked={state.defaultServiceId === service.id} onChange={() => dispatch({ type: "service", value: service.id })} /><span className="choice-check" /><span className="choice-content"><strong>{service.name}</strong><small>{service.description ?? "Professional mobile car care at your location."}</small><em>≈ {service.estimated_duration_minutes} min</em></span><b>{formatMoney(service.price_minor, service.currency_code)}</b></label>)}</div><StepActions next={() => dispatch({ type: "step", value: "details" })} disabled={!state.defaultServiceId} /></>;
}

function DetailsStep({ state, dispatch }: StepProps) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const next = () => { const found = contactErrors(state.contact, state.location); setErrors(found); if (!Object.keys(found).length) dispatch({ type: "step", value: "vehicles" }); else setTimeout(() => document.querySelector<HTMLElement>("[aria-invalid=true]")?.focus(), 0); };
  const contactField = (field: keyof typeof state.contact, label: string, type = "text", autocomplete?: string) => <label><span>{label}</span><input type={type} autoComplete={autocomplete} value={state.contact[field]} aria-invalid={!!errors[field]} aria-describedby={errors[field] ? `${field}-error` : undefined} onChange={(event) => dispatch({ type: "contact", field, value: event.target.value })} /><FieldError id={`${field}-error`}>{errors[field]}</FieldError></label>;
  return <><StepIntro eyebrow="About you" title="Where should we meet you?" copy="We’ll use these details only to arrange and confirm your service." /><div className="form-section"><h2>Contact details</h2><div className="form-grid two">{contactField("first_name", "First name", "text", "given-name")}{contactField("surname", "Surname", "text", "family-name")}{contactField("email", "Email address", "email", "email")}{contactField("phone", "Phone number", "tel", "tel")}</div></div><div className="form-section"><h2>Service location</h2><div className="form-grid"><label><span>Written address</span><textarea rows={3} value={state.location.written_address} aria-invalid={!!errors.written_address} aria-describedby={errors.written_address ? "address-error" : undefined} onChange={(event) => dispatch({ type: "location", field: "written_address", value: event.target.value })} /><FieldError id="address-error">{errors.written_address}</FieldError></label><label><span>Google Maps or location link</span><input type="url" placeholder="https://maps.google.com/…" value={state.location.location_url} aria-invalid={!!errors.location_url} aria-describedby={errors.location_url ? "map-error" : "map-hint"} onChange={(event) => dispatch({ type: "location", field: "location_url", value: event.target.value })} /><small id="map-hint" className="field-hint">Paste a share link so the team can find you precisely.</small><FieldError id="map-error">{errors.location_url}</FieldError></label><label><span>Location notes <em>Optional</em></span><textarea rows={2} placeholder="Parking access, building entrance, or anything useful" value={state.location.instructions} onChange={(event) => dispatch({ type: "location", field: "instructions", value: event.target.value })} /></label></div></div><StepActions back={() => dispatch({ type: "step", value: "service" })} next={next} /></>;
}

function VehiclesStep({ state, dispatch }: StepProps) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const next = () => { const found = vehicleErrors(state.vehicles); setErrors(found); if (!Object.keys(found).length) dispatch({ type: "step", value: "review" }); else setTimeout(() => document.querySelector<HTMLElement>("[aria-invalid=true]")?.focus(), 0); };
  return <><StepIntro eyebrow="Your vehicles" title={state.vehicles.length === 1 ? "Tell us about your car." : `Tell us about your ${state.vehicles.length} cars.`} copy="Add every vehicle in this visit and choose the right service for each." /><div className="vehicle-stack">{state.vehicles.map((vehicle, index) => <VehicleCard key={vehicle.key} vehicle={vehicle} index={index} services={state.catalogue!.services} errors={errors} canRemove={state.vehicles.length > 1} dispatch={dispatch} />)}</div><button className="add-button" type="button" onClick={() => dispatch({ type: "add_vehicle" })}><span>+</span> Add another vehicle</button>{state.vehicles.length >= state.catalogue!.settings.multi_vehicle_threshold && <div className="inline-notice"><strong>More time, reserved automatically.</strong><span>The scheduling service will find a consecutive window for this visit.</span></div>}<StepActions back={() => dispatch({ type: "step", value: "details" })} next={next} /></>;
}

function VehicleCard({ vehicle, index, services, errors, canRemove, dispatch }: { vehicle: Vehicle; index: number; services: Service[]; errors: Record<string, string>; canRemove: boolean; dispatch: StepProps["dispatch"] }) {
  const update = (field: keyof Vehicle, value: string) => dispatch({ type: "vehicle", key: vehicle.key, field, value });
  const input = (field: keyof Vehicle, label: string, placeholder = "") => <label><span>{label}</span><input value={vehicle[field]} placeholder={placeholder} aria-invalid={!!errors[`${vehicle.key}.${field}`]} aria-describedby={errors[`${vehicle.key}.${field}`] ? `${vehicle.key}-${field}-error` : undefined} onChange={(event) => update(field, event.target.value)} /><FieldError id={`${vehicle.key}-${field}-error`}>{errors[`${vehicle.key}.${field}`]}</FieldError></label>;
  return <fieldset className="vehicle-card"><legend><span>Vehicle {index + 1}</span>{canRemove && <button type="button" onClick={() => dispatch({ type: "remove_vehicle", key: vehicle.key })}>Remove</button>}</legend><div className="form-grid two">{input("make", "Make", "Toyota")}{input("model", "Model", "Camry")}{input("year", "Year (optional)", "2024")}<label><span>Vehicle type</span><select value={vehicle.vehicle_type} aria-invalid={!!errors[`${vehicle.key}.vehicle_type`]} onChange={(event) => update("vehicle_type", event.target.value)}><option value="">Select a type</option>{vehicleTypes.map((type) => <option key={type} value={type.toLowerCase()}>{type}</option>)}</select><FieldError id={`${vehicle.key}-vehicle_type-error`}>{errors[`${vehicle.key}.vehicle_type`]}</FieldError></label>{input("colour", "Colour (optional)")}{input("plate_number", "Plate number (optional)")}</div><label><span>Service for this vehicle</span><select value={vehicle.service_id} aria-invalid={!!errors[`${vehicle.key}.service_id`]} onChange={(event) => update("service_id", event.target.value)}>{services.map((service) => <option key={service.id} value={service.id}>{service.name} — {formatMoney(service.price_minor, service.currency_code)}</option>)}</select><FieldError id={`${vehicle.key}-service_id-error`}>{errors[`${vehicle.key}.service_id`]}</FieldError></label><label><span>Vehicle notes <em>Optional</em></span><textarea rows={2} value={vehicle.notes} onChange={(event) => update("notes", event.target.value)} /></label></fieldset>;
}

function ReviewStep({ state, dispatch }: StepProps) {
  const services = new Map(state.catalogue!.services.map((service) => [service.id, service]));
  const estimate = state.vehicles.reduce((total, vehicle) => total + (services.get(vehicle.service_id)?.price_minor ?? 0), 0);
  return <><StepIntro eyebrow="Review" title="Everything look right?" copy="Check the visit before choosing a date. Final pricing is confirmed by the server when you book." /><div className="review-sections"><ReviewBlock title="Contact" action={() => dispatch({ type: "step", value: "details" })}><strong>{state.contact.first_name} {state.contact.surname}</strong><span>{state.contact.email}</span><span>{state.contact.phone}</span></ReviewBlock><ReviewBlock title="Location" action={() => dispatch({ type: "step", value: "details" })}><strong>{state.location.written_address}</strong><a href={state.location.location_url} target="_blank" rel="noreferrer">Open map link ↗</a>{state.location.instructions && <span>{state.location.instructions}</span>}</ReviewBlock><ReviewBlock title={`Vehicles · ${state.vehicles.length}`} action={() => dispatch({ type: "step", value: "vehicles" })}>{state.vehicles.map((vehicle) => <div className="review-vehicle" key={vehicle.key}><span><strong>{vehicle.make} {vehicle.model}</strong><small>{[vehicle.year, vehicle.colour, vehicle.plate_number].filter(Boolean).join(" · ")}</small></span><b>{services.get(vehicle.service_id)?.name}</b></div>)}</ReviewBlock><div className="estimate-row"><span><strong>Estimated total</strong><small>Calculated from current catalogue prices</small></span><b>{formatMoney(estimate, state.catalogue!.settings.currency_code)}</b></div></div><StepActions back={() => dispatch({ type: "step", value: "vehicles" })} next={() => dispatch({ type: "step", value: "schedule" })} nextLabel="Choose a time" /></>;
}

function ReviewBlock({ title, action, children }: { title: string; action: () => void; children: React.ReactNode }) { return <section className="review-block"><header><h2>{title}</h2><button type="button" onClick={action}>Edit</button></header><div>{children}</div></section>; }

function ScheduleStep({ state, dispatch }: StepProps) {
  const timezone = state.catalogue!.settings.timezone;
  const today = todayInTimezone(timezone);
  const [year, month] = today.split("-").map(Number);
  const [visibleMonth, setVisibleMonth] = useState({ year, monthIndex: month - 1 });
  const [availabilityLoading, setAvailabilityLoading] = useState(false);
  const [error, setError] = useState("");
  const [holding, setHolding] = useState(false);
  const loadAvailability = async (selectedDate: string) => { setAvailabilityLoading(true); setError(""); try { dispatch({ type: "availability", value: await getAvailability(selectedDate, state.vehicles.length) }); } catch (reason) { setError(friendlyError(reason)); } finally { setAvailabilityLoading(false); } };
  const chooseDate = (value: string) => { dispatch({ type: "date", value }); void loadAvailability(value); };
  const proceed = async () => {
    const slot = state.availability?.slots.find((item) => item.time === state.selectedSlotTime);
    if (!slot) return;
    setHolding(true); setError("");
    try { const hold = await createHold({ date: state.selectedDate, start_time: slot.time, vehicle_count: state.vehicles.length, resource_id: slot.resources[0]?.resource_id }); dispatch({ type: "hold", value: hold }); dispatch({ type: "step", value: "payment" }); }
    catch (reason) { setError(reason instanceof ApiError && reason.isSchedulingConflict ? "That time was just taken. We refreshed availability so you can choose another." : friendlyError(reason)); if (reason instanceof ApiError && reason.isSchedulingConflict) await loadAvailability(state.selectedDate); }
    finally { setHolding(false); }
  };
  const moveMonth = (delta: number) => { const date = new Date(Date.UTC(visibleMonth.year, visibleMonth.monthIndex + delta, 1)); setVisibleMonth({ year: date.getUTCFullYear(), monthIndex: date.getUTCMonth() }); };
  const monthLabel = new Intl.DateTimeFormat("en-AE", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(Date.UTC(visibleMonth.year, visibleMonth.monthIndex, 1)));
  const currentMonthKey = `${year}-${String(month).padStart(2, "0")}`;
  const visibleMonthKey = `${visibleMonth.year}-${String(visibleMonth.monthIndex + 1).padStart(2, "0")}`;
  return <><StepIntro eyebrow="Your schedule" title="When should we come?" copy={`Times shown in ${timezone.replace("_", " ")}. Availability is live and your time is held on the next step.`} /><div className="schedule-grid"><div className="calendar"><header><button type="button" aria-label="Previous month" disabled={visibleMonthKey <= currentMonthKey} onClick={() => moveMonth(-1)}>←</button><h2>{monthLabel}</h2><button type="button" aria-label="Next month" onClick={() => moveMonth(1)}>→</button></header><div className="weekday-row" aria-hidden="true">{["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => <span key={day}>{day}</span>)}</div><div className="calendar-grid">{calendarCells(visibleMonth.year, visibleMonth.monthIndex).map((day, index) => day ? <button type="button" key={day} className={state.selectedDate === dateKey(visibleMonth.year, visibleMonth.monthIndex, day) ? "selected" : ""} disabled={dateKey(visibleMonth.year, visibleMonth.monthIndex, day) < today} aria-label={new Intl.DateTimeFormat("en-AE", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" }).format(new Date(Date.UTC(visibleMonth.year, visibleMonth.monthIndex, day)))} onClick={() => chooseDate(dateKey(visibleMonth.year, visibleMonth.monthIndex, day))}>{day}</button> : <span key={`empty-${index}`} />)}</div></div><div className="times-panel"><h2>{state.selectedDate ? "Available starts" : "Choose a date"}</h2>{availabilityLoading && <div className="slot-loading"><span className="spinner dark" /> Checking live times…</div>}{!availabilityLoading && state.availability && <><div className="slot-grid">{state.availability.slots.map((slot) => <SlotButton key={slot.time} slot={slot} selected={state.selectedSlotTime === slot.time} timezone={timezone} onSelect={() => dispatch({ type: "slot", value: slot.time })} />)}</div>{!state.availability.slots.some((slot) => slot.available) && <p className="empty-copy">No times are available on this date. Please try another day.</p>}</>}{!state.selectedDate && <p className="empty-copy">Select a date to see real-time availability.</p>}</div></div>{state.availability?.required_slot_count && state.availability.required_slot_count > 1 ? <div className="inline-notice"><strong>A consecutive window is included.</strong><span>For {state.vehicles.length} vehicles, the selected start reserves {state.availability.required_slot_count} back-to-back slots. The end time comes directly from live availability.</span></div> : null}{error && <div className="error-banner" role="alert">{error}</div>}<StepActions back={() => dispatch({ type: "step", value: "review" })} next={proceed} nextLabel="Reserve this time" busy={holding} disabled={!state.selectedSlotTime} /></>;
}

function SlotButton({ slot, selected, timezone, onSelect }: { slot: AvailabilitySlot; selected: boolean; timezone: string; onSelect: () => void }) {
  const time = new Intl.DateTimeFormat("en-AE", { timeZone: timezone, hour: "numeric", minute: "2-digit" });
  return <button type="button" className={selected ? "slot selected" : "slot"} disabled={!slot.available} aria-pressed={selected} title={slot.available ? undefined : slot.unavailable_reason?.replaceAll("_", " ").toLowerCase()} onClick={onSelect}><strong>{time.format(new Date(slot.starts_at))}</strong>{slot.required_slot_count > 1 && <small>until {time.format(new Date(slot.ends_at))}</small>}</button>;
}

function PaymentStep({ state, dispatch }: StepProps) {
  const [choice, setChoice] = useState<"pay_after_service" | "pay_now">("pay_after_service");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const idempotencyKey = useRef("");
  const expiresAt = state.hold?.expires_at;
  const maxHoldSeconds = state.catalogue!.settings.hold_duration_minutes * 60;
  const remainingSeconds = () => expiresAt ? Math.min(maxHoldSeconds, Math.max(0, Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000))) : 0;
  const [seconds, setSeconds] = useState(remainingSeconds);
  useEffect(() => {
    const update = () => setSeconds(expiresAt ? Math.min(maxHoldSeconds, Math.max(0, Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000))) : 0);
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [expiresAt, maxHoldSeconds]);
  const submit = async () => { if (!state.hold || choice !== "pay_after_service") return; setSubmitting(true); setError(""); idempotencyKey.current ||= crypto.randomUUID(); try { dispatch({ type: "booking", value: await createBooking({ hold_token: state.hold.hold_token, contact: state.contact, location: state.location, vehicles: state.vehicles, payment_choice: "pay_after_service", idempotencyKey: idempotencyKey.current }) }); } catch (reason) { setError(friendlyError(reason)); if (reason instanceof ApiError && reason.isSchedulingConflict) dispatch({ type: "step", value: "schedule" }); } finally { setSubmitting(false); } };
  const estimate = state.vehicles.reduce((total, vehicle) => total + (state.catalogue!.services.find((service) => service.id === vehicle.service_id)?.price_minor ?? 0), 0);
  return <><StepIntro eyebrow="Payment" title="How would you like to pay?" copy="Your slot is temporarily reserved while you confirm." />{state.hold && <div className={seconds < 60 ? "hold-timer urgent" : "hold-timer"}><span>Time reserved</span><strong>{String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(seconds % 60).padStart(2, "0")}</strong></div>}<div className="payment-layout"><div className="choice-list"><label className={choice === "pay_after_service" ? "choice-card selected" : "choice-card"}><input type="radio" name="payment" checked={choice === "pay_after_service"} onChange={() => setChoice("pay_after_service")} /><span className="choice-check" /><span className="choice-content"><strong>Pay after service</strong><small>Pay the team once your wash is complete.</small><em>Available now</em></span></label><label className={choice === "pay_now" ? "choice-card selected" : "choice-card"}><input type="radio" name="payment" checked={choice === "pay_now"} onChange={() => setChoice("pay_now")} /><span className="choice-check" /><span className="choice-content"><strong>Pay now</strong><small>Online card payments are not connected yet.</small><em>Coming soon</em></span></label>{choice === "pay_now" && <div className="inline-notice warning" role="status"><strong>Online payment isn’t available yet.</strong><span>Choose “Pay after service” to complete this booking. No card details are collected.</span></div>}</div><aside className="payment-summary"><span>Booking estimate</span><strong>{formatMoney(estimate, state.catalogue!.settings.currency_code)}</strong><p>{state.vehicles.length} {state.vehicles.length === 1 ? "vehicle" : "vehicles"}</p>{state.hold && <small>{formatSchedule(state.hold.starts_at, state.hold.ends_at, state.catalogue!.settings.timezone)}</small>}</aside></div>{error && <div className="error-banner" role="alert">{error}</div>}<StepActions back={() => dispatch({ type: "step", value: "schedule" })} next={submit} nextLabel="Confirm booking" busy={submitting} disabled={choice !== "pay_after_service" || seconds <= 0} /></>;
}

function Confirmation({ state }: { state: typeof initialBookingState }) {
  const booking = state.booking!;
  return <main className="confirmation-page"><div className="confirmation-burst" aria-hidden="true">✓</div><section className="confirmation-card"><p className="eyebrow"><span /> Booking confirmed</p><h1>We’ll see you there, {booking.customer_first_name}.</h1><p className="confirmation-lead">Your wash is booked. Keep the reference below handy.</p><div className="reference-box"><span>Booking reference</span><strong>{booking.reference}</strong></div><div className="confirmation-grid"><div><span>Date & time</span><strong>{formatSchedule(booking.scheduled_start, booking.scheduled_end, state.catalogue!.settings.timezone)}</strong></div><div><span>Payment</span><strong>Pay after service · {booking.payment_status}</strong></div><div><span>Location</span><strong>{booking.written_address}</strong><a href={booking.location_url} target="_blank" rel="noreferrer">Open map ↗</a></div><div><span>Total confirmed</span><strong>{formatMoney(booking.total_amount_minor, booking.currency_code)}</strong></div></div><div className="confirmed-vehicles"><h2>{booking.vehicles.length === 1 ? "Vehicle & service" : "Vehicles & services"}</h2>{booking.vehicles.map((vehicle, index) => <div key={`${vehicle.make}-${vehicle.model}-${index}`}><span><strong>{vehicle.make} {vehicle.model}</strong><small>{[vehicle.year, vehicle.colour, vehicle.plate_number].filter(Boolean).join(" · ")}</small></span><b>{vehicle.service_name}</b></div>)}</div><div className="confirmation-actions"><Link className="button" href={`/manage#${booking.management_token}`}>Manage booking <span aria-hidden="true">→</span></Link><Link className="button button-ghost" href="/">Back to home</Link></div><p className="confirmation-note">A confirmation notification has been queued for {state.contact.email}.</p></section></main>;
}

function LoadingPanel() { return <div className="loading-panel"><span className="spinner dark" /><strong>Preparing your booking</strong><p>Loading live services and business settings…</p></div>; }
function ErrorPanel({ message, onRetry }: { message: string; onRetry: () => void }) { return <div className="loading-panel"><strong>We couldn’t load booking details.</strong><p>{message}</p><button className="button" type="button" onClick={onRetry}>Try again</button></div>; }

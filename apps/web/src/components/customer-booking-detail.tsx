"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./auth-provider";
import { CustomerStatus } from "./customer-status";
import {
  ApiError,
  createHold,
  getAvailability,
  getCustomerBooking,
  requestCustomerCancellation,
  rescheduleCustomerBooking,
} from "@/lib/api";
import { localizedCustomerError } from "@/lib/customer-error";
import { formatMoney, formatSchedule, todayInTimezone } from "@/lib/dates";
import type { Availability, CustomerBookingDetail as BookingDetail } from "@/lib/types";
import { useI18n } from "./i18n-provider";
import { localizePaymentStatus, localizeServiceName } from "@/lib/i18n";

export function CustomerBookingDetail({ bookingId }: { bookingId: string }) {
  const { language, locale, t } = useI18n();
  const translationRef = useRef(t);
  const languageRef = useRef(language);
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [booking, setBooking] = useState<BookingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [rescheduleOpen, setRescheduleOpen] = useState(false);
  const [date, setDate] = useState("");
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [selectedTime, setSelectedTime] = useState("");
  const [busy, setBusy] = useState(false);
  const cancellationKey = useRef("");
  const rescheduleKey = useRef("");
  const rescheduleHoldToken = useRef("");
  useEffect(() => { translationRef.current = t; languageRef.current = language; }, [language, t]);

  useEffect(() => {
    if (!authLoading && !user) router.replace(`/login?returnTo=${encodeURIComponent(`/account/bookings/${bookingId}`)}`);
  }, [authLoading, bookingId, router, user]);

  useEffect(() => {
    let active = true;
    if (authLoading || !user) return;
    void getCustomerBooking(bookingId).then((value) => {
      if (active) { setBooking(value); setError(""); }
    }).catch((reason) => {
      if (active) setError(reason instanceof ApiError && reason.status === 404 ? translationRef.current("account.bookingMissing") : localizedCustomerError(reason, languageRef.current, translationRef.current));
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [authLoading, bookingId, user]);

  async function cancelBooking() {
    if (!booking) return;
    setBusy(true); setError("");
    cancellationKey.current ||= crypto.randomUUID();
    try {
      setBooking(await requestCustomerCancellation(booking.id, cancelReason, cancellationKey.current));
      setCancelOpen(false);
    } catch (reason) { setError(localizedCustomerError(reason, language, t)); }
    finally { setBusy(false); }
  }

  async function loadTimes(value: string) {
    if (!booking) return;
    setDate(value); setSelectedTime(""); setAvailability(null); setError("");
    rescheduleKey.current = "";
    rescheduleHoldToken.current = "";
    if (!value) return;
    try { setAvailability(await getAvailability(value, booking.vehicle_count)); }
    catch (reason) { setError(localizedCustomerError(reason, language, t)); }
  }

  async function reschedule() {
    if (!booking || !availability || !selectedTime) return;
    const slot = availability.slots.find((candidate) => candidate.time === selectedTime);
    if (!slot) return;
    setBusy(true); setError("");
    rescheduleKey.current ||= crypto.randomUUID();
    try {
      if (!rescheduleHoldToken.current) {
        const hold = await createHold({
          date,
          start_time: slot.time,
          vehicle_count: booking.vehicle_count,
          resource_id: slot.resources[0]?.resource_id,
        });
        rescheduleHoldToken.current = hold.hold_token;
      }
      setBooking(await rescheduleCustomerBooking(
        booking.id,
        rescheduleHoldToken.current,
        rescheduleKey.current,
      ));
      rescheduleHoldToken.current = "";
      rescheduleKey.current = "";
      setRescheduleOpen(false); setAvailability(null); setSelectedTime("");
    } catch (reason) {
      setError(reason instanceof ApiError && reason.isSchedulingConflict ? t("account.timeUnavailable") : localizedCustomerError(reason, language, t));
      if (reason instanceof ApiError && reason.isSchedulingConflict) {
        rescheduleHoldToken.current = "";
        rescheduleKey.current = "";
        await loadTimes(date);
      }
    } finally { setBusy(false); }
  }

  if (authLoading || loading || !user) return <main className="account-page"><div className="loading-panel"><span className="spinner dark" /><strong>{t("account.loadingBooking")}</strong></div></main>;
  if (!booking) return <main className="account-page"><div className="shell account-empty"><h1>{t("account.bookingUnavailable")}</h1><p>{error}</p><Link className="button" href="/account">{t("account.back")}</Link></div></main>;

  return <main className="account-page"><div className="shell customer-detail-shell">
    <Link className="quiet-link" href="/account"><span className="directional-icon" aria-hidden="true">←</span> {t("account.allBookings")}</Link>
    <section className="customer-detail-card">
      <header className="customer-detail-heading"><div><p className="eyebrow"><span /> {t("account.booking")}</p><h1>{booking.reference}</h1></div><CustomerStatus status={booking.status} compact /></header>
      <CustomerStatus status={booking.status} />
      {booking.estimated_arrival_at && <div className="inline-notice"><strong>{t("account.estimatedArrival")}</strong><span>{new Intl.DateTimeFormat(locale, { hour: "numeric", minute: "2-digit", timeZone: booking.timezone }).format(new Date(booking.estimated_arrival_at))}</span></div>}
      {error && <div className="error-banner" role="alert">{error}</div>}
      <div className="customer-detail-grid">
        <div><span>{t("common.dateTime")}</span><strong>{formatSchedule(booking.scheduled_start, booking.scheduled_end, booking.timezone, locale)}</strong></div>
        <div><span>{t("common.payment")}</span><strong>{booking.payment_choice === "pay_after_service" ? t("booking.payment.payAfter") : t("booking.payment.payNow")} · {localizePaymentStatus(language, booking.payment_status)}</strong></div>
        <div><span>{t("common.location")}</span><strong>{booking.written_address}</strong><a href={booking.location_url} target="_blank" rel="noreferrer">{t("account.openMaps")} ↗</a></div>
        <div><span>{t("common.total")}</span><strong>{formatMoney(booking.total_amount_minor, booking.currency_code, locale)}</strong></div>
      </div>
      <section className="customer-vehicles"><h2>{t("account.vehicleServices")}</h2>{booking.vehicles.map((vehicle, index) => <div key={`${vehicle.make}-${vehicle.model}-${index}`}><span><strong>{vehicle.make} {vehicle.model}</strong><small className="bidi-ltr">{[vehicle.year, vehicle.colour, vehicle.plate_number].filter(Boolean).join(" · ")}</small></span><b>{localizeServiceName(language, vehicle.service_name)}</b></div>)}</section>
      {(booking.cancellation_eligible || booking.reschedule_eligible) && <div className="customer-actions">
        {booking.reschedule_eligible && <button className="button button-ghost" type="button" onClick={() => { setRescheduleOpen(true); setCancelOpen(false); }}>{t("account.reschedule")}</button>}
        {booking.cancellation_eligible && <button className="button button-danger" type="button" onClick={() => { setCancelOpen(true); setRescheduleOpen(false); }}>{t("account.cancelRequest")}</button>}
      </div>}
      {cancelOpen && <section className="action-dialog" role="dialog" aria-modal="true" aria-labelledby="cancel-title"><h2 id="cancel-title">{t("account.cancelTitle")}</h2><p>{t("account.cancelCopy")}</p><label><span>{t("account.reason")} <em>{t("common.optional")}</em></span><textarea rows={3} value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} /></label><div><button className="button button-ghost" type="button" onClick={() => setCancelOpen(false)}>{t("account.keep")}</button><button className="button button-danger" type="button" disabled={busy} onClick={() => void cancelBooking()}>{busy ? t("account.sending") : t("account.send")}</button></div></section>}
      {rescheduleOpen && <section className="action-dialog" role="dialog" aria-modal="true" aria-labelledby="reschedule-title"><h2 id="reschedule-title">{t("account.rescheduleTitle")}</h2><p>{t("account.rescheduleCopy")}</p><label><span>{t("account.newDate")}</span><input type="date" min={todayInTimezone(booking.timezone)} value={date} onChange={(event) => void loadTimes(event.target.value)} /></label>{availability && <div className="reschedule-slots">{availability.slots.filter((slot) => slot.available).map((slot) => <button type="button" className={selectedTime === slot.time ? "slot selected" : "slot"} key={slot.time} aria-pressed={selectedTime === slot.time} onClick={() => { setSelectedTime(slot.time); rescheduleHoldToken.current = ""; rescheduleKey.current = ""; }}>{new Intl.DateTimeFormat(locale, { timeZone: booking.timezone, hour: "numeric", minute: "2-digit" }).format(new Date(slot.starts_at))}</button>)}</div>}<div><button className="button button-ghost" type="button" onClick={() => setRescheduleOpen(false)}>{t("common.close")}</button><button className="button" type="button" disabled={busy || !selectedTime} onClick={() => void reschedule()}>{busy ? t("account.rescheduling") : t("account.confirmTime")}</button></div></section>}
    </section>
  </div></main>;
}

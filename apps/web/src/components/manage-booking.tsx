"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { BrandMark } from "./brand-mark";
import { getManagedBooking, requestCancellation } from "@/lib/api";
import { localizedCustomerError } from "@/lib/customer-error";
import { formatMoney, formatSchedule } from "@/lib/dates";
import type { ManagedBooking } from "@/lib/types";
import { LanguageSwitcher, useI18n } from "./i18n-provider";
import { localizePaymentStatus, localizeServiceName } from "@/lib/i18n";

export function ManageBooking() {
  const { language, locale, t } = useI18n();
  const translationRef = useRef(t);
  const languageRef = useRef(language);
  const [booking, setBooking] = useState<ManagedBooking | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reason, setReason] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const idempotencyKey = useRef("");
  const token = useRef("");
  useEffect(() => { translationRef.current = t; languageRef.current = language; }, [language, t]);
  useEffect(() => {
    token.current = decodeURIComponent(window.location.hash.slice(1));
    if (!token.current) {
      Promise.resolve().then(() => {
        setError(translationRef.current("manage.incomplete"));
        setLoading(false);
      });
      return;
    }
    getManagedBooking(token.current).then(setBooking).catch((value) => setError(localizedCustomerError(value, languageRef.current, translationRef.current))).finally(() => setLoading(false));
  }, []);
  const submit = async (event: FormEvent) => { event.preventDefault(); setSubmitting(true); setError(""); idempotencyKey.current ||= crypto.randomUUID(); try { const result = await requestCancellation(token.current, reason, idempotencyKey.current); setBooking(result.booking); setShowForm(false); } catch (value) { setError(localizedCustomerError(value, language, t)); } finally { setSubmitting(false); } };
  const statusLabels: Partial<Record<string, string>> = { confirmed: t("status.confirmed"), en_route: t("status.driverEnRoute"), arrived: t("status.driverArrived"), in_progress: t("status.inProgress"), completed: t("status.completed"), cancelled: t("status.cancelled"), cancellation_requested: t("status.cancellationRequested") };

  return <>
    <header className="booking-header"><div className="shell"><Link className="brand" href="/" aria-label={t("brand.home")}><BrandMark /></Link><LanguageSwitcher compact /><Link className="quiet-link" href="/">{t("manage.home")}</Link></div></header>
    <main className="manage-page"><section className="shell manage-card">
      {loading && <div className="loading-panel"><span className="spinner dark" /><strong>{t("manage.finding")}</strong></div>}
      {!loading && !booking && <div className="loading-panel"><strong>{t("manage.cannotOpen")}</strong><p>{error || t("manage.invalid")}</p><Link className="button" href="/contact">{t("manage.contact")}</Link></div>}
      {booking && <>
        <p className="eyebrow"><span /> {t("manage.title")}</p>
        <div className="manage-title"><div><h1>{booking.reference}</h1><p>{t("manage.bookedFor", { name: `${booking.customer_first_name} ${booking.customer_surname}` })}</p></div><span className={`status-pill status-${booking.status}`}>{statusLabels[booking.status] ?? booking.status.replaceAll("_", " ")}</span></div>
        {booking.cancellation_status === "requested" && <div className="inline-notice"><strong>{t("manage.cancellationRequested")}</strong><span>{t("manage.cancellationPending")}</span></div>}
        <div className="confirmation-grid manage-summary">
          <div><span>{t("common.dateTime")}</span><strong>{formatSchedule(booking.scheduled_start, booking.scheduled_end, booking.timezone, locale)}</strong></div>
          <div><span>{t("common.payment")}</span><strong>{booking.payment_choice === "pay_after_service" ? t("booking.payment.payAfter") : t("booking.payment.payNow")} · {localizePaymentStatus(language, booking.payment_status)}</strong></div>
          <div><span>{t("common.location")}</span><strong>{booking.written_address}</strong><a href={booking.location_url} target="_blank" rel="noreferrer">{t("booking.confirmation.openMap")} ↗</a></div>
          <div><span>{t("manage.confirmedTotal")}</span><strong>{formatMoney(booking.total_amount_minor, booking.currency_code, locale)}</strong></div>
        </div>
        <div className="confirmed-vehicles"><h2>{t("manage.visitDetails")}</h2>{booking.vehicles.map((vehicle, index) => <div key={`${vehicle.make}-${vehicle.model}-${index}`}><span><strong>{vehicle.make} {vehicle.model}</strong><small className="bidi-ltr">{[vehicle.year, vehicle.colour, vehicle.plate_number].filter(Boolean).join(" · ")}</small></span><b>{localizeServiceName(language, vehicle.service_name)}</b></div>)}</div>
        <section className="cancellation-panel"><h2>{t("manage.plansChanged")}</h2>{booking.cancellation_eligible ? <><p>{t("manage.cancellationCopy", { cutoff: new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone: booking.timezone }).format(new Date(booking.cancellation_cutoff_at)) })}</p>{!showForm ? <button className="button button-danger" type="button" onClick={() => setShowForm(true)}>{t("account.cancelRequest")}</button> : <form onSubmit={submit}><label><span>{t("account.reason")} <em>{t("common.optional")}</em></span><textarea rows={3} maxLength={2000} value={reason} onChange={(event) => setReason(event.target.value)} /></label><div className="step-actions"><button className="button button-ghost" type="button" onClick={() => setShowForm(false)}>{t("account.keep")}</button><button className="button button-danger" disabled={submitting} type="submit">{submitting ? t("account.sending") : t("account.send")}</button></div></form>}</> : <p>{t("manage.cancellationUnavailable")}</p>}</section>
        {error && <div className="error-banner" role="alert">{error}</div>}
      </>}
    </section></main>
  </>;
}

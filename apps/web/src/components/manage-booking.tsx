"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { BrandMark } from "./brand-mark";
import { friendlyError, getManagedBooking, requestCancellation } from "@/lib/api";
import { formatMoney, formatSchedule } from "@/lib/dates";
import type { ManagedBooking } from "@/lib/types";

export function ManageBooking() {
  const [booking, setBooking] = useState<ManagedBooking | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reason, setReason] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const idempotencyKey = useRef("");
  const token = useRef("");
  useEffect(() => {
    token.current = decodeURIComponent(window.location.hash.slice(1));
    if (!token.current) {
      Promise.resolve().then(() => {
        setError("This secure booking link is incomplete.");
        setLoading(false);
      });
      return;
    }
    getManagedBooking(token.current).then(setBooking).catch((value) => setError(friendlyError(value))).finally(() => setLoading(false));
  }, []);
  const submit = async (event: FormEvent) => { event.preventDefault(); setSubmitting(true); setError(""); idempotencyKey.current ||= crypto.randomUUID(); try { const result = await requestCancellation(token.current, reason, idempotencyKey.current); setBooking(result.booking); setShowForm(false); } catch (value) { setError(friendlyError(value)); } finally { setSubmitting(false); } };

  return <><header className="booking-header"><div className="shell"><Link className="brand" href="/"><BrandMark /><span>AbdWash</span></Link><Link className="quiet-link" href="/">Home</Link></div></header><main className="manage-page"><section className="shell manage-card">{loading && <div className="loading-panel"><span className="spinner dark" /><strong>Finding your booking</strong></div>}{!loading && !booking && <div className="loading-panel"><strong>We couldn’t open this booking.</strong><p>{error || "The secure link may be invalid or no longer available."}</p><Link className="button" href="/contact">Contact support</Link></div>}{booking && <><p className="eyebrow"><span /> Manage booking</p><div className="manage-title"><div><h1>{booking.reference}</h1><p>Booked for {booking.customer_first_name} {booking.customer_surname}</p></div><span className={`status-pill status-${booking.status}`}>{booking.status.replaceAll("_", " ")}</span></div>{booking.cancellation_status === "requested" && <div className="inline-notice"><strong>Cancellation requested</strong><span>Your booking is still active until the AbdWash team reviews and approves the request.</span></div>}<div className="confirmation-grid manage-summary"><div><span>Date & time</span><strong>{formatSchedule(booking.scheduled_start, booking.scheduled_end, booking.timezone)}</strong></div><div><span>Payment</span><strong>{booking.payment_choice === "pay_after_service" ? "Pay after service" : "Pay now"} · {booking.payment_status}</strong></div><div><span>Location</span><strong>{booking.written_address}</strong><a href={booking.location_url} target="_blank" rel="noreferrer">Open map ↗</a></div><div><span>Confirmed total</span><strong>{formatMoney(booking.total_amount_minor, booking.currency_code)}</strong></div></div><div className="confirmed-vehicles"><h2>Visit details</h2>{booking.vehicles.map((vehicle, index) => <div key={`${vehicle.make}-${vehicle.model}-${index}`}><span><strong>{vehicle.make} {vehicle.model}</strong><small>{[vehicle.year, vehicle.colour, vehicle.plate_number].filter(Boolean).join(" · ")}</small></span><b>{vehicle.service_name}</b></div>)}</div><section className="cancellation-panel"><h2>Plans changed?</h2>{booking.cancellation_eligible ? <><p>Requests can be made until {new Intl.DateTimeFormat("en-AE", { dateStyle: "medium", timeStyle: "short", timeZone: booking.timezone }).format(new Date(booking.cancellation_cutoff_at))}. A request does not cancel the booking until it is approved.</p>{!showForm ? <button className="button button-danger" type="button" onClick={() => setShowForm(true)}>Request cancellation</button> : <form onSubmit={submit}><label><span>Reason <em>Optional</em></span><textarea rows={3} maxLength={2000} value={reason} onChange={(event) => setReason(event.target.value)} /></label><div className="step-actions"><button className="button button-ghost" type="button" onClick={() => setShowForm(false)}>Keep booking</button><button className="button button-danger" disabled={submitting} type="submit">{submitting ? "Sending request…" : "Send request"}</button></div></form>}</> : <p>A new cancellation request isn’t available for this booking. The cutoff is 24 hours before the service start, and all requests require review.</p>}</section>{error && <div className="error-banner" role="alert">{error}</div>}</>}</section></main></>;
}

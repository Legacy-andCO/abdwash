"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./auth-provider";
import { CustomerStatus } from "./customer-status";
import { useCustomerBookings } from "@/lib/use-customer-bookings";
import { formatMoney, formatSchedule } from "@/lib/dates";
import type { CustomerBookingSummary } from "@/lib/types";

function BookingCard({ booking, featured = false }: { booking: CustomerBookingSummary; featured?: boolean }) {
  const vehicle = booking.vehicles[0];
  return <article className={featured ? "account-booking-card featured" : "account-booking-card"}>
    <div><CustomerStatus status={booking.status} compact /><h2>{booking.reference}</h2><p>{formatSchedule(booking.scheduled_start, booking.scheduled_end, "Asia/Dubai")}</p><small>{booking.written_address}</small>{vehicle && <span className="booking-service-summary">{vehicle.make} {vehicle.model} · {vehicle.service_name}</span>}<span className="booking-payment-summary">Payment: {booking.payment_status.replaceAll("_", " ")}</span></div>
    <div className="account-card-meta"><span>{booking.vehicle_count} {booking.vehicle_count === 1 ? "vehicle" : "vehicles"}</span><strong>{formatMoney(booking.total_amount_minor, booking.currency_code)}</strong><Link className="text-link" href={`/account/bookings/${booking.id}`}>View booking →</Link></div>
  </article>;
}

export function AccountBookings() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { bookings, loading, error, refresh } = useCustomerBookings();
  const firstName = typeof user?.user_metadata.first_name === "string" ? user.user_metadata.first_name : "there";
  const upcoming = bookings.filter((booking) => booking.category === "upcoming");
  const cancelled = bookings.filter((booking) => booking.category === "cancelled");
  const past = bookings.filter((booking) => booking.category === "past");

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login?returnTo=%2Faccount");
  }, [authLoading, router, user]);

  if (authLoading || !user) return <div className="loading-panel"><span className="spinner dark" /><strong>Loading your account…</strong></div>;

  return <main className="account-page"><div className="shell account-shell">
    <header className="account-heading"><div><p className="eyebrow"><span /> Your account</p><h1>Hi, {firstName}.</h1><p>Track upcoming visits and manage changes from one place.</p></div><Link className="button" href="/book">Book another wash</Link></header>
    {error && <div className="error-banner" role="alert">{error}<button type="button" onClick={() => void refresh()}>Try again</button></div>}
    {!error && loading && !bookings.length && <div className="loading-panel"><span className="spinner dark" /><strong>Loading bookings…</strong></div>}
    {!loading && !bookings.length && <section className="account-empty"><h2>No linked bookings yet.</h2><p>Bookings you make while logged in will appear here. Guest bookings stay available through their secure management link.</p><Link className="button" href="/book">Book your first wash</Link></section>}
    {upcoming.length > 0 && <section className="account-group"><h2>Your upcoming wash</h2><BookingCard booking={upcoming[0]} featured />{upcoming.slice(1).map((booking) => <BookingCard booking={booking} key={booking.id} />)}</section>}
    {past.length > 0 && <section className="account-group"><h2>Past bookings</h2>{past.map((booking) => <BookingCard booking={booking} key={booking.id} />)}</section>}
    {cancelled.length > 0 && <section className="account-group"><h2>Cancelled bookings</h2>{cancelled.map((booking) => <BookingCard booking={booking} key={booking.id} />)}</section>}
  </div></main>;
}

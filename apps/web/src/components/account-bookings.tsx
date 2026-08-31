"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./auth-provider";
import { CustomerStatus } from "./customer-status";
import { useCustomerBookings } from "@/lib/use-customer-bookings";
import { formatMoney, formatSchedule, TRIFECTA_TIME_ZONE } from "@/lib/dates";
import type { CustomerBookingSummary } from "@/lib/types";
import { useI18n } from "./i18n-provider";
import { localizePaymentStatus, localizeServiceName } from "@/lib/i18n";

function BookingCard({ booking, featured = false }: { booking: CustomerBookingSummary; featured?: boolean }) {
  const { language, locale, t } = useI18n();
  const vehicle = booking.vehicles[0];
  return <article className={featured ? "account-booking-card featured" : "account-booking-card"}>
    <div><CustomerStatus status={booking.status} compact /><h2>{booking.reference}</h2><p>{formatSchedule(booking.scheduled_start, booking.scheduled_end, TRIFECTA_TIME_ZONE, locale)}</p><small>{booking.written_address}</small>{vehicle && <span className="booking-service-summary">{vehicle.make} {vehicle.model} · {localizeServiceName(language, vehicle.service_name)}</span>}<span className="booking-payment-summary">{t("account.paymentSummary", { status: localizePaymentStatus(language, booking.payment_status) })}</span></div>
    <div className="account-card-meta"><span>{booking.vehicle_count} {booking.vehicle_count === 1 ? t("common.vehicle") : t("common.vehicles")}</span><strong>{formatMoney(booking.total_amount_minor, booking.currency_code, locale)}</strong><Link className="text-link" href={`/account/bookings/${booking.id}`}>{t("account.view")} <span className="directional-icon" aria-hidden="true">→</span></Link></div>
  </article>;
}

export function AccountBookings() {
  const { t } = useI18n();
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

  if (authLoading || !user) return <div className="loading-panel"><span className="spinner dark" /><strong>{t("account.loading")}</strong></div>;

  return <main className="account-page"><div className="shell account-shell">
    <header className="account-heading"><div><p className="eyebrow"><span /> {t("account.heading")}</p><h1>{t("account.hello", { name: firstName })}</h1><p>{t("account.copy")}</p></div><Link className="button" href="/book">{t("account.bookAnother")}</Link></header>
    {error && <div className="error-banner" role="alert">{t("account.loadError")}<button type="button" onClick={() => void refresh()}>{t("common.tryAgain")}</button></div>}
    {!error && loading && !bookings.length && <div className="loading-panel"><span className="spinner dark" /><strong>{t("account.loadingBookings")}</strong></div>}
    {!loading && !bookings.length && <section className="account-empty"><h2>{t("account.emptyTitle")}</h2><p>{t("account.emptyCopy")}</p><Link className="button" href="/book">{t("account.firstBooking")}</Link></section>}
    {upcoming.length > 0 && <section className="account-group"><h2>{t("account.upcoming")}</h2><BookingCard booking={upcoming[0]} featured />{upcoming.slice(1).map((booking) => <BookingCard booking={booking} key={booking.id} />)}</section>}
    {past.length > 0 && <section className="account-group"><h2>{t("account.past")}</h2>{past.map((booking) => <BookingCard booking={booking} key={booking.id} />)}</section>}
    {cancelled.length > 0 && <section className="account-group"><h2>{t("account.cancelled")}</h2>{cancelled.map((booking) => <BookingCard booking={booking} key={booking.id} />)}</section>}
  </div></main>;
}

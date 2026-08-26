"use client";

import Link from "next/link";
import { useAuth } from "./auth-provider";
import { CustomerStatus } from "./customer-status";
import { useCustomerBookings } from "@/lib/use-customer-bookings";
import { formatSchedule } from "@/lib/dates";
import { useI18n } from "./i18n-provider";

export function HomeBookingStatus() {
  const { locale, t } = useI18n();
  const { user } = useAuth();
  const { bookings } = useCustomerBookings({ polling: true });
  if (!user) return null;
  const active = bookings
    .filter((booking) => booking.category === "upcoming")
    .sort((left, right) => Date.parse(left.scheduled_start) - Date.parse(right.scheduled_start))[0];
  if (!active) return null;
  const statusLabels: Partial<Record<string, string>> = { confirmed: t("status.confirmed"), en_route: t("status.driverEnRoute"), arrived: t("status.driverArrived"), in_progress: t("status.inProgress"), completed: t("status.completed"), cancelled: t("status.cancelled"), cancellation_requested: t("status.cancellationRequested") };
  return <section className="shell home-status-card" aria-label={t("account.upcomingStatus")}>
    <div><CustomerStatus status={active.status} compact /><h2>{statusLabels[active.status.key] ?? active.status.label}</h2><p>{formatSchedule(active.scheduled_start, active.scheduled_end, "Asia/Dubai", locale)}</p>{active.estimated_arrival_at && <strong>{t("account.estimatedArrival")}: {new Intl.DateTimeFormat(locale, { hour: "numeric", minute: "2-digit", timeZone: "Asia/Dubai" }).format(new Date(active.estimated_arrival_at))}</strong>}</div>
    <Link className="button button-ghost" href={`/account/bookings/${active.id}`}>{t("account.view")}</Link>
  </section>;
}

"use client";

import Link from "next/link";
import { useAuth } from "./auth-provider";
import { CustomerStatus } from "./customer-status";
import { useCustomerBookings } from "@/lib/use-customer-bookings";
import { formatSchedule } from "@/lib/dates";

export function HomeBookingStatus() {
  const { user } = useAuth();
  const { bookings } = useCustomerBookings({ polling: true });
  if (!user) return null;
  const active = bookings
    .filter((booking) => booking.category === "upcoming")
    .sort((left, right) => Date.parse(left.scheduled_start) - Date.parse(right.scheduled_start))[0];
  if (!active) return null;
  return <section className="shell home-status-card" aria-label="Upcoming booking status">
    <div><CustomerStatus status={active.status} compact /><h2>{active.status.label}</h2><p>{formatSchedule(active.scheduled_start, active.scheduled_end, "Asia/Dubai")}</p></div>
    <Link className="button button-ghost" href={`/account/bookings/${active.id}`}>View booking</Link>
  </section>;
}

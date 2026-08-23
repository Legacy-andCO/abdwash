export const BOOKING_STATES = [
  "pending_payment",
  "confirmed",
  "cancellation_requested",
  "cancelled",
  "completed",
] as const;

export type BookingState = (typeof BOOKING_STATES)[number];
export type PaymentChoice = "pay_now" | "pay_after_service";


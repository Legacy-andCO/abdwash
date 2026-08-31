import type {
  Availability,
  Booking,
  Catalogue,
  Contact,
  BillingDetails,
  CustomerBookingDetail,
  CustomerBookingSummary,
  CustomerContext,
  CustomerProfileBootstrap,
  CustomerSavedAddress,
  CustomerSavedVehicle,
  Hold,
  Location,
  ManagedBooking,
  RevenueInvoice,
  Vehicle,
} from "./types";
import { normalizePhone } from "./phone";
import { getSupabaseAccessToken } from "./supabase-client";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

type ApiErrorBody = {
  code?: string;
  message?: string;
  request_id?: string;
  details?: Record<string, unknown>;
};

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
    public readonly requestId?: string,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }

  get isSchedulingConflict() {
    return [
      "SLOT_UNAVAILABLE",
      "CONSECUTIVE_SLOT_UNAVAILABLE",
      "HOLD_EXPIRED",
      "NO_TEAM_CAPACITY",
      "BOOKING_ASSIGNMENT_CHANGED",
    ].includes(this.code);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  const headers = new Headers(init?.headers);
  const accessToken = await getSupabaseAccessToken();
  if (accessToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  if (init?.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers,
    });
  } catch {
    throw new ApiError(
      "NETWORK_ERROR",
      "We could not reach Trifecta. Check your connection and try again.",
      0,
    );
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new ApiError(
      body.code ?? "REQUEST_FAILED",
      body.message ?? "Something went wrong. Please try again.",
      response.status,
      body.request_id,
      body.details,
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

let cataloguePromise: Promise<Catalogue> | undefined;

export function getCatalogue(): Promise<Catalogue> {
  cataloguePromise ??= request<Catalogue>("/api/v1/public/catalogue").catch(
    (error) => {
      cataloguePromise = undefined;
      throw error;
    },
  );
  return cataloguePromise;
}

export function getAvailability(
  date: string,
  vehicleCount: number,
  selections?: { serviceIds: string[]; addonIds: string[] },
): Promise<Availability> {
  const params = new URLSearchParams({
    date,
    vehicle_count: String(vehicleCount),
  });
  selections?.serviceIds.forEach((id) => params.append("service_id", id));
  selections?.addonIds.forEach((id) => params.append("addon_id", id));
  return request<Availability>(`/api/v1/public/availability?${params}`);
}

export function createHold(input: {
  date: string;
  start_time: string;
  vehicle_count: number;
  service_ids?: string[];
  addon_ids?: string[];
}): Promise<Hold> {
  return request<Hold>("/api/v1/public/holds", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createBooking(input: {
  hold_token: string;
  contact: Contact;
  billing?: BillingDetails;
  location: Location;
  vehicles: Vehicle[];
  payment_choice: "pay_after_service";
  idempotencyKey: string;
}): Promise<Booking> {
  const body = {
    hold_token: input.hold_token,
    contact: {
      first_name: input.contact.first_name,
      surname: input.contact.surname,
      email: input.contact.email.trim() || null,
      phone:
        normalizePhone(input.contact.phone, input.contact.phone_country) ??
        input.contact.phone,
    },
    location: {
      written_address: input.location.written_address,
      location_url: input.location.location_url,
      latitude: input.location.latitude,
      longitude: input.location.longitude,
      instructions: input.location.instructions,
    },
    billing:
      input.billing?.company_name.trim() && input.billing.billing_address.trim()
        ? {
            company_name: input.billing.company_name,
            billing_address: input.billing.billing_address,
            tax_registration_number:
              input.billing.tax_registration_number || null,
          }
        : null,
    vehicles: input.vehicles.map(({ key: _key, year, ...vehicle }) => ({
      ...vehicle,
      year: year ? Number(year) : null,
    })),
    payment_choice: input.payment_choice,
    source: "web",
  };
  return request<Booking>("/api/v1/public/bookings", {
    method: "POST",
    headers: { "Idempotency-Key": input.idempotencyKey },
    body: JSON.stringify(body),
  });
}

export function getManagedBooking(token: string): Promise<ManagedBooking> {
  return request<ManagedBooking>("/api/v1/public/bookings/manage", {
    headers: { "X-Booking-Management-Token": token },
  });
}

export function getManagedInvoice(
  token: string,
  invoiceId: string,
): Promise<RevenueInvoice> {
  return request<RevenueInvoice>(
    `/api/v1/public/bookings/manage/invoices/${encodeURIComponent(invoiceId)}`,
    { headers: { "X-Booking-Management-Token": token } },
  );
}

export function requestCancellation(
  token: string,
  reason: string,
  idempotencyKey: string,
) {
  return request<{ id: string; status: string; booking: ManagedBooking }>(
    "/api/v1/public/bookings/manage/cancellation-requests",
    {
      method: "POST",
      headers: {
        "Idempotency-Key": idempotencyKey,
        "X-Booking-Management-Token": token,
      },
      body: JSON.stringify({ reason: reason || null }),
    },
  );
}

export function getCustomerContext(): Promise<CustomerContext> {
  return request<CustomerContext>("/api/v1/customer/context");
}

export function getCustomerProfile(): Promise<CustomerProfileBootstrap> {
  return request<CustomerProfileBootstrap>("/api/v1/customer/profile");
}

export function updateCustomerProfile(input: {
  first_name: string;
  surname: string;
  phone: string;
}) {
  return request<CustomerProfileBootstrap>("/api/v1/customer/profile", {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export type SavedAddressInput = Omit<
  CustomerSavedAddress,
  "id" | "location_instructions"
> & { instructions: string };
export const createCustomerAddress = (input: SavedAddressInput) =>
  request<CustomerSavedAddress>("/api/v1/customer/addresses", {
    method: "POST",
    body: JSON.stringify(input),
  });
export const updateCustomerAddress = (id: string, input: SavedAddressInput) =>
  request<CustomerSavedAddress>(
    `/api/v1/customer/addresses/${encodeURIComponent(id)}`,
    { method: "PATCH", body: JSON.stringify(input) },
  );
export const deleteCustomerAddress = (id: string) =>
  request<void>(`/api/v1/customer/addresses/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });

export type SavedVehicleInput = Omit<
  CustomerSavedVehicle,
  "id" | "plate_number"
> & {
  plate_number: string;
};
export const createCustomerVehicle = (input: SavedVehicleInput) =>
  request<CustomerSavedVehicle>("/api/v1/customer/vehicles", {
    method: "POST",
    body: JSON.stringify(input),
  });
export const updateCustomerVehicle = (id: string, input: SavedVehicleInput) =>
  request<CustomerSavedVehicle>(
    `/api/v1/customer/vehicles/${encodeURIComponent(id)}`,
    { method: "PATCH", body: JSON.stringify(input) },
  );
export const deleteCustomerVehicle = (id: string) =>
  request<void>(`/api/v1/customer/vehicles/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });

export async function getCustomerBookings(): Promise<CustomerBookingSummary[]> {
  const response = await request<{ bookings: CustomerBookingSummary[] }>(
    "/api/v1/customer/bookings",
  );
  return response.bookings;
}

export function getCustomerBooking(
  bookingId: string,
): Promise<CustomerBookingDetail> {
  return request<CustomerBookingDetail>(
    `/api/v1/customer/bookings/${encodeURIComponent(bookingId)}`,
  );
}

export async function requestCustomerCancellation(
  bookingId: string,
  reason: string,
  idempotencyKey: string,
): Promise<CustomerBookingDetail> {
  const response = await request<{ booking: CustomerBookingDetail }>(
    `/api/v1/customer/bookings/${encodeURIComponent(bookingId)}/cancellation-requests`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ reason: reason || null }),
    },
  );
  return response.booking;
}

export async function rescheduleCustomerBooking(
  bookingId: string,
  holdToken: string,
  idempotencyKey: string,
): Promise<CustomerBookingDetail> {
  const response = await request<{ booking: CustomerBookingDetail }>(
    `/api/v1/customer/bookings/${encodeURIComponent(bookingId)}/reschedule`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ hold_token: holdToken }),
    },
  );
  return response.booking;
}

export function friendlyError(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Something unexpected happened. Please try again.";
}

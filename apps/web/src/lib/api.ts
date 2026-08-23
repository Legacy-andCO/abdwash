import type {
  Availability,
  Booking,
  Catalogue,
  Contact,
  Hold,
  Location,
  ManagedBooking,
  Vehicle,
} from "./types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

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
    return ["SLOT_UNAVAILABLE", "CONSECUTIVE_SLOT_UNAVAILABLE", "HOLD_EXPIRED"].includes(
      this.code,
    );
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  const headers = new Headers(init?.headers);
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
      "We could not reach AbdWash. Check your connection and try again.",
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
  return (await response.json()) as T;
}

let cataloguePromise: Promise<Catalogue> | undefined;

export function getCatalogue(): Promise<Catalogue> {
  cataloguePromise ??= request<Catalogue>("/api/v1/public/catalogue").catch((error) => {
    cataloguePromise = undefined;
    throw error;
  });
  return cataloguePromise;
}

export function getAvailability(date: string, vehicleCount: number): Promise<Availability> {
  const params = new URLSearchParams({ date, vehicle_count: String(vehicleCount) });
  return request<Availability>(`/api/v1/public/availability?${params}`);
}

export function createHold(input: {
  date: string;
  start_time: string;
  vehicle_count: number;
  resource_id?: string;
}): Promise<Hold> {
  return request<Hold>("/api/v1/public/holds", { method: "POST", body: JSON.stringify(input) });
}

export function createBooking(input: {
  hold_token: string;
  contact: Contact;
  location: Location;
  vehicles: Vehicle[];
  payment_choice: "pay_after_service";
  idempotencyKey: string;
}): Promise<Booking> {
  const body = {
    hold_token: input.hold_token,
    contact: input.contact,
    location: input.location,
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

export function requestCancellation(token: string, reason: string, idempotencyKey: string) {
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

export function friendlyError(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Something unexpected happened. Please try again.";
}

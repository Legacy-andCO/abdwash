import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, createBooking, createHold, friendlyError, getAvailability, getCatalogue, getCustomerBooking, getCustomerBookings, getManagedBooking, requestCancellation, requestCustomerCancellation, rescheduleCustomerBooking } from "./api";
import { emptyVehicle } from "./booking-state";
import * as supabaseClient from "./supabase-client";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function bookingInput(idempotencyKey: string) {
  return {
    hold_token: "h".repeat(40),
    contact: { first_name: "A", surname: "B", email: "a@b.com", phone: "050 123 4567", phone_country: "AE" as const },
    location: { written_address: "Abu Dhabi", location_url: "https://maps.google.com/x", latitude: 24.45, longitude: 54.37, instructions: "" },
    vehicles: [{ ...emptyVehicle("service"), make: "Toyota", model: "Camry", vehicle_type: "sedan" }],
    payment_choice: "pay_after_service" as const,
    idempotencyKey,
  };
}

describe("central API client", () => {
  it("does not send JSON content type for catalogue GET requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ services: [] })); vi.stubGlobal("fetch", fetchMock);
    await getCatalogue();
    const headers = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(headers.has("Content-Type")).toBe(false);
  });
  it("requests availability once with date and vehicle count", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ slots: [] })); vi.stubGlobal("fetch", fetchMock);
    await getAvailability("2030-01-02", 3);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toContain("date=2030-01-02&vehicle_count=3");
    const headers = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(headers.has("Content-Type")).toBe(false);
  });
  it("submits a hold using the selected server resource", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ hold_token: "x" }, 201)); vi.stubGlobal("fetch", fetchMock);
    await createHold({ date: "2030-01-02", start_time: "09:00:00", vehicle_count: 1, resource_id: "team" });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ resource_id: "team", vehicle_count: 1 });
    const headers = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(headers.get("Content-Type")).toBe("application/json");
  });
  it("never sends a client-computed total or paid state", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: "booking" }, 201)); vi.stubGlobal("fetch", fetchMock);
    await createBooking(bookingInput("booking-key"));
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.total_amount_minor).toBeUndefined();
    expect(body.payment_status).toBeUndefined();
    expect(body.contact.phone).toBe("+971501234567");
    expect(body.contact.phone_country).toBeUndefined();
    expect(body.location).toMatchObject({ latitude: 24.45, longitude: 54.37 });
  });
  it("attaches the booking idempotency key", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}, 201)); vi.stubGlobal("fetch", fetchMock);
    await createBooking(bookingInput("stable-key"));
    const headers = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("Idempotency-Key")).toBe("stable-key");
  });
  it("maps structured backend failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ code: "HOLD_EXPIRED", message: "Expired", request_id: "r" }, 409)));
    await expect(createHold({ date: "2030-01-02", start_time: "09:00:00", vehicle_count: 1 })).rejects.toMatchObject({ code: "HOLD_EXPIRED", status: 409 });
  });
  it("identifies scheduling conflicts for refresh behavior", () => expect(new ApiError("SLOT_UNAVAILABLE", "Taken", 409).isSchedulingConflict).toBe(true));
  it("provides a safe fallback for unknown UI errors", () => expect(friendlyError(new Error("internal"))).not.toContain("internal"));
  it("sends management secrets in a header rather than the URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ reference: "AW-1" })); vi.stubGlobal("fetch", fetchMock);
    await getManagedBooking("secure-token");
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/api/v1/public/bookings/manage");
    const headers = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(headers.get("X-Booking-Management-Token")).toBe("secure-token");
    expect(headers.has("Content-Type")).toBe(false);
  });
  it("protects cancellation requests with both management and idempotency headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: "requested" }, 201)); vi.stubGlobal("fetch", fetchMock);
    await requestCancellation("secure-token", "Plans changed", "cancel-key");
    const headers = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("X-Booking-Management-Token")).toBe("secure-token");
    expect(headers.get("Idempotency-Key")).toBe("cancel-key");
  });
  it("attaches a Supabase bearer token when a customer session exists", async () => {
    vi.spyOn(supabaseClient, "getSupabaseAccessToken").mockResolvedValue("customer-access-token");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ slots: [] })); vi.stubGlobal("fetch", fetchMock);
    await getAvailability("2030-01-02", 1);
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get("Authorization")).toBe("Bearer customer-access-token");
  });
  it("keeps guest requests free of an Authorization header", async () => {
    vi.spyOn(supabaseClient, "getSupabaseAccessToken").mockResolvedValue(null);
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ hold_token: "x" }, 201)); vi.stubGlobal("fetch", fetchMock);
    await createHold({ date: "2030-01-02", start_time: "09:00:00", vehicle_count: 1 });
    expect(new Headers(fetchMock.mock.calls[0][1].headers).has("Authorization")).toBe(false);
  });
  it("uses authenticated customer routes without placing identity in the URL", async () => {
    vi.spyOn(supabaseClient, "getSupabaseAccessToken").mockResolvedValue("customer-token");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ bookings: [] }))
      .mockResolvedValueOnce(jsonResponse({ id: "booking-id" }));
    vi.stubGlobal("fetch", fetchMock);
    await getCustomerBookings();
    await getCustomerBooking("booking-id");
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/api/v1/customer/bookings");
    expect(fetchMock.mock.calls[1][0]).toBe("http://localhost:8000/api/v1/customer/bookings/booking-id");
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get("Authorization")).toBe("Bearer customer-token");
  });
  it("protects customer cancellation and reschedule mutations with idempotency", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ booking: { id: "booking-id" } }))
      .mockResolvedValueOnce(jsonResponse({ booking: { id: "booking-id" } }));
    vi.stubGlobal("fetch", fetchMock);
    await requestCustomerCancellation("booking-id", "Changed plans", "customer-cancel-key");
    await rescheduleCustomerBooking("booking-id", "h".repeat(40), "customer-reschedule-key");
    const cancelHeaders = new Headers(fetchMock.mock.calls[0][1].headers);
    const rescheduleHeaders = new Headers(fetchMock.mock.calls[1][1].headers);
    expect(cancelHeaders.get("Idempotency-Key")).toBe("customer-cancel-key");
    expect(rescheduleHeaders.get("Idempotency-Key")).toBe("customer-reschedule-key");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ hold_token: "h".repeat(40) });
  });
});

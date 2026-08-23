import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, createBooking, createHold, friendlyError, getAvailability, getManagedBooking, requestCancellation } from "./api";
import { emptyVehicle } from "./booking-state";

afterEach(() => vi.unstubAllGlobals());

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("central API client", () => {
  it("requests availability once with date and vehicle count", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ slots: [] })); vi.stubGlobal("fetch", fetchMock);
    await getAvailability("2030-01-02", 3);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toContain("date=2030-01-02&vehicle_count=3");
  });
  it("submits a hold using the selected server resource", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ hold_token: "x" }, 201)); vi.stubGlobal("fetch", fetchMock);
    await createHold({ date: "2030-01-02", start_time: "09:00:00", vehicle_count: 1, resource_id: "team" });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ resource_id: "team", vehicle_count: 1 });
  });
  it("never sends a client-computed total or paid state", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: "booking" }, 201)); vi.stubGlobal("fetch", fetchMock);
    await createBooking({ hold_token: "h".repeat(40), contact: { first_name: "A", surname: "B", email: "a@b.com", phone: "+971500000" }, location: { written_address: "Dubai", location_url: "https://maps.google.com/x", instructions: "" }, vehicles: [{ ...emptyVehicle("service"), make: "Toyota", model: "Camry", vehicle_type: "sedan" }], payment_choice: "pay_after_service", idempotencyKey: "booking-key" });
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.total_amount_minor).toBeUndefined();
    expect(body.payment_status).toBeUndefined();
  });
  it("attaches the booking idempotency key", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}, 201)); vi.stubGlobal("fetch", fetchMock);
    await createBooking({ hold_token: "h".repeat(40), contact: { first_name: "A", surname: "B", email: "a@b.com", phone: "+971500000" }, location: { written_address: "Dubai", location_url: "https://maps.google.com/x", instructions: "" }, vehicles: [{ ...emptyVehicle("service"), make: "Toyota", model: "Camry", vehicle_type: "sedan" }], payment_choice: "pay_after_service", idempotencyKey: "stable-key" });
    expect(fetchMock.mock.calls[0][1].headers["Idempotency-Key"]).toBe("stable-key");
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
    expect(fetchMock.mock.calls[0][1].headers["X-Booking-Management-Token"]).toBe("secure-token");
  });
  it("protects cancellation requests with both management and idempotency headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: "requested" }, 201)); vi.stubGlobal("fetch", fetchMock);
    await requestCancellation("secure-token", "Plans changed", "cancel-key");
    expect(fetchMock.mock.calls[0][1].headers).toMatchObject({ "X-Booking-Management-Token": "secure-token", "Idempotency-Key": "cancel-key" });
  });
});

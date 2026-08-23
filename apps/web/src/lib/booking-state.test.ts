import { describe, expect, it } from "vitest";
import {
  bookingReducer,
  calculateEstimate,
  canSubmitPayment,
  contactErrors,
  emptyVehicle,
  initialBookingState,
  vehicleErrors,
} from "./booking-state";
import type { Catalogue } from "./types";

const catalogue: Catalogue = {
  business_name: "AbdWash",
  settings: {
    timezone: "Asia/Dubai", currency_code: "AED", opening_time: "09:00:00",
    closing_time: "21:00:00", slot_duration_minutes: 120, multi_vehicle_threshold: 3,
    multi_vehicle_required_slots: 2, hold_duration_minutes: 10, cancellation_cutoff_hours: 24,
  },
  services: [
    { id: "basic", name: "Basic", description: null, price_minor: 5000, currency_code: "AED", estimated_duration_minutes: 60 },
    { id: "full", name: "Full", description: null, price_minor: 9000, currency_code: "AED", estimated_duration_minutes: 120 },
  ],
};

describe("booking state", () => {
  it("loads the first real service as the default", () => {
    expect(bookingReducer(initialBookingState, { type: "catalogue", value: catalogue }).defaultServiceId).toBe("basic");
  });
  it("preserves a service selected from the landing page", () => {
    const selected = { ...initialBookingState, defaultServiceId: "full" };
    expect(bookingReducer(selected, { type: "catalogue", value: catalogue }).defaultServiceId).toBe("full");
  });
  it("updates the first vehicle when the starting service changes", () => {
    expect(bookingReducer(initialBookingState, { type: "service", value: "full" }).vehicles[0].service_id).toBe("full");
  });
  it("adds another vehicle with the selected default service", () => {
    const state = { ...initialBookingState, defaultServiceId: "full" };
    expect(bookingReducer(state, { type: "add_vehicle" }).vehicles[1].service_id).toBe("full");
  });
  it("removes only the requested vehicle", () => {
    const second = emptyVehicle("full");
    const state = { ...initialBookingState, vehicles: [initialBookingState.vehicles[0], second] };
    expect(bookingReducer(state, { type: "remove_vehicle", key: second.key }).vehicles).toHaveLength(1);
  });
  it("clears stale availability and hold when a vehicle changes", () => {
    const state = { ...initialBookingState, hold: { hold_token: "secret", resource_id: "r", starts_at: "", ends_at: "", expires_at: "", required_slot_count: 1 } };
    expect(bookingReducer(state, { type: "vehicle", key: state.vehicles[0].key, field: "make", value: "Toyota" }).hold).toBeNull();
  });
  it("accepts complete contact and secure location details", () => {
    expect(contactErrors({ first_name: "A", surname: "B", email: "a@b.com", phone: "+971 50 000 0000" }, { written_address: "Dubai Marina", location_url: "https://maps.google.com/x", instructions: "" })).toEqual({});
  });
  it("rejects an invalid email address", () => {
    expect(contactErrors({ first_name: "A", surname: "B", email: "wrong", phone: "+971500000" }, { written_address: "Dubai Marina", location_url: "https://maps.google.com/x", instructions: "" }).email).toBeTruthy();
  });
  it("rejects a non-secure map link", () => {
    expect(contactErrors({ first_name: "A", surname: "B", email: "a@b.com", phone: "+971500000" }, { written_address: "Dubai Marina", location_url: "http://maps.google.com/x", instructions: "" }).location_url).toContain("secure");
  });
  it("requires core details and a service on every vehicle", () => {
    expect(Object.keys(vehicleErrors([emptyVehicle()]))).toHaveLength(4);
  });
  it("rejects a year outside the supported range", () => {
    const vehicle = { ...emptyVehicle("basic"), make: "Toyota", model: "Camry", vehicle_type: "sedan", year: "1800" };
    expect(vehicleErrors([vehicle])[`${vehicle.key}.year`]).toBeTruthy();
  });
  it("supports a different service for each vehicle", () => {
    const first = { ...emptyVehicle("basic"), make: "A", model: "A", vehicle_type: "sedan" };
    const second = { ...emptyVehicle("full"), make: "B", model: "B", vehicle_type: "suv" };
    expect([first.service_id, second.service_id]).toEqual(["basic", "full"]);
  });
  it("calculates a display-only estimate from catalogue prices", () => {
    expect(calculateEstimate([{ ...emptyVehicle("basic") }, { ...emptyVehicle("full") }], catalogue)).toBe(14000);
  });
  it("allows submission only for the implemented payment path", () => {
    expect(canSubmitPayment("pay_after_service")).toBe(true);
    expect(canSubmitPayment("pay_now")).toBe(false);
  });
});

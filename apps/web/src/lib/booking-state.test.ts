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
import type { Catalogue, Contact, Location } from "./types";

const contact: Contact = {
  first_name: "A",
  surname: "B",
  email: "a@b.com",
  phone: "+971 50 123 4567",
  phone_country: "AE",
};
const location: Location = {
  written_address: "Abu Dhabi",
  location_url: "https://maps.google.com/x",
  latitude: null,
  longitude: null,
  instructions: "Meet at the lobby",
};

const catalogue: Catalogue = {
  business_name: "AbdWash",
  settings: {
    timezone: "Asia/Dubai",
    currency_code: "AED",
    opening_time: "09:00:00",
    closing_time: "21:00:00",
    slot_duration_minutes: 120,
    multi_vehicle_threshold: 3,
    multi_vehicle_required_slots: 2,
    hold_duration_minutes: 10,
    cancellation_cutoff_hours: 24,
  },
  services: [
    {
      id: "basic",
      name: "Basic",
      description: null,
      price_minor: 5000,
      currency_code: "AED",
      estimated_duration_minutes: 60,
    },
    {
      id: "full",
      name: "Full",
      description: null,
      price_minor: 9000,
      currency_code: "AED",
      estimated_duration_minutes: 120,
    },
  ],
};

describe("booking state", () => {
  const customerProfile = {
    authenticated_email: "noor@example.com",
    profile: {
      id: "profile-1",
      first_name: "Noor",
      surname: "Ali",
      email: "noor@example.com",
      phone: "+971501234567",
    },
    addresses: [
      {
        id: "address-1",
        label: "Home",
        written_address: "Al Reem Island, Abu Dhabi",
        location_url: "https://maps.google.com/x",
        latitude: 24.49,
        longitude: 54.4,
        location_instructions: "Gate 2",
        is_default: true,
      },
    ],
    vehicles: [
      {
        id: "vehicle-1",
        make: "BMW",
        model: "X5",
        year: 2024,
        vehicle_type: "suv",
        colour: "Black",
        plate_number: "ABC 123",
        notes: null,
      },
    ],
  };
  it("prefills contact and the default saved location", () => {
    const state = bookingReducer(initialBookingState, {
      type: "customer_bootstrap",
      value: customerProfile,
    });
    expect(state.contact.first_name).toBe("Noor");
    expect(state.location.written_address).toContain("Al Reem");
  });
  it("selects another saved location without mutating the bootstrap data", () => {
    const state = bookingReducer(
      { ...initialBookingState, customerProfile },
      {
        type: "saved_location",
        value: {
          ...customerProfile.addresses[0],
          written_address: "Yas Island",
        },
      },
    );
    expect(state.location.written_address).toBe("Yas Island");
    expect(state.customerProfile?.addresses[0].written_address).toContain(
      "Al Reem",
    );
  });
  it("populates a booking vehicle with its authorized saved id", () => {
    const state = bookingReducer(
      { ...initialBookingState, defaultServiceId: "basic", customerProfile },
      { type: "saved_vehicle", value: customerProfile.vehicles[0] },
    );
    expect(state.vehicles[0]).toMatchObject({
      vehicle_id: "vehicle-1",
      make: "BMW",
      service_id: "basic",
    });
  });
  it("loads the first real service as the default", () => {
    expect(
      bookingReducer(initialBookingState, {
        type: "catalogue",
        value: catalogue,
      }).defaultServiceId,
    ).toBe("basic");
  });
  it("preserves a service selected from the landing page", () => {
    const selected = { ...initialBookingState, defaultServiceId: "full" };
    expect(
      bookingReducer(selected, { type: "catalogue", value: catalogue })
        .defaultServiceId,
    ).toBe("full");
  });
  it("updates the first vehicle when the starting service changes", () => {
    expect(
      bookingReducer(initialBookingState, { type: "service", value: "full" })
        .vehicles[0].service_id,
    ).toBe("full");
  });
  it("adds another vehicle with the selected default service", () => {
    const state = { ...initialBookingState, defaultServiceId: "full" };
    expect(
      bookingReducer(state, { type: "add_vehicle" }).vehicles[1].service_id,
    ).toBe("full");
  });
  it("removes only the requested vehicle", () => {
    const second = emptyVehicle("full");
    const state = {
      ...initialBookingState,
      vehicles: [initialBookingState.vehicles[0], second],
    };
    expect(
      bookingReducer(state, { type: "remove_vehicle", key: second.key })
        .vehicles,
    ).toHaveLength(1);
  });
  it("clears stale availability and hold when a vehicle changes", () => {
    const state = {
      ...initialBookingState,
      hold: {
        hold_token: "secret",
        resource_id: "r",
        starts_at: "",
        ends_at: "",
        expires_at: "",
        required_slot_count: 1,
      },
    };
    expect(
      bookingReducer(state, {
        type: "vehicle",
        key: state.vehicles[0].key,
        field: "make",
        value: "Toyota",
      }).hold,
    ).toBeNull();
  });
  it("accepts complete contact and secure location details", () => {
    expect(contactErrors(contact, location)).toEqual({});
  });
  it("rejects an invalid email address", () => {
    expect(
      contactErrors({ ...contact, email: "wrong" }, location).email,
    ).toBeTruthy();
  });
  it("rejects a non-secure map link", () => {
    expect(
      contactErrors(contact, {
        ...location,
        location_url: "http://maps.google.com/x",
      }).location_url,
    ).toContain("supported");
  });
  it("requires core details and a service on every vehicle", () => {
    expect(Object.keys(vehicleErrors([emptyVehicle()]))).toHaveLength(5);
  });
  it("blocks legacy saved details until notes and plate are completed", () => {
    expect(
      contactErrors(contact, { ...location, instructions: "" }).instructions,
    ).toBeTruthy();
    const vehicle = {
      ...emptyVehicle("basic"),
      make: "Toyota",
      model: "Camry",
      vehicle_type: "sedan",
    };
    expect(
      vehicleErrors([vehicle])[`${vehicle.key}.plate_number`],
    ).toBeTruthy();
  });
  it("rejects a year outside the supported range", () => {
    const vehicle = {
      ...emptyVehicle("basic"),
      make: "Toyota",
      model: "Camry",
      vehicle_type: "sedan",
      year: "1800",
    };
    expect(vehicleErrors([vehicle])[`${vehicle.key}.year`]).toBeTruthy();
  });
  it("supports a different service for each vehicle", () => {
    const first = {
      ...emptyVehicle("basic"),
      make: "A",
      model: "A",
      vehicle_type: "sedan",
    };
    const second = {
      ...emptyVehicle("full"),
      make: "B",
      model: "B",
      vehicle_type: "suv",
    };
    expect([first.service_id, second.service_id]).toEqual(["basic", "full"]);
  });
  it("calculates a display-only estimate from catalogue prices", () => {
    expect(
      calculateEstimate(
        [{ ...emptyVehicle("basic") }, { ...emptyVehicle("full") }],
        catalogue,
      ),
    ).toBe(14000);
  });
  it("applies a specific reward to only one eligible vehicle", () => {
    const first = { ...emptyVehicle("basic"), loyalty_reward_id: "reward-1" };
    const second = { ...emptyVehicle("full") };
    expect(calculateEstimate([first, second], catalogue)).toBe(9000);
  });
  it("clears a reward when its vehicle service changes", () => {
    const vehicle = { ...emptyVehicle("basic"), loyalty_reward_id: "reward-1" };
    const state = bookingReducer(
      { ...initialBookingState, vehicles: [vehicle] },
      { type: "vehicle", key: vehicle.key, field: "service_id", value: "full" },
    );
    expect(state.vehicles[0].loyalty_reward_id).toBeUndefined();
  });
  it("allows submission only for the implemented payment path", () => {
    expect(canSubmitPayment("pay_after_service")).toBe(true);
    expect(canSubmitPayment("pay_now")).toBe(false);
  });
});

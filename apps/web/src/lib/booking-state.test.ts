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
  business_name: "Trifecta",
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
      {
        id: "vehicle-2",
        make: "Toyota",
        model: "Land Cruiser",
        year: 2023,
        vehicle_type: "suv",
        colour: "White",
        plate_number: "XYZ 456",
        notes: "Roof rack",
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
    const bookingVehicle = {
      ...initialBookingState.vehicles[0],
      service_id: "full",
      loyalty_reward_id: "reward-1",
    };
    const state = bookingReducer(
      {
        ...initialBookingState,
        defaultServiceId: "basic",
        customerProfile,
        vehicles: [bookingVehicle],
      },
      {
        type: "apply_saved_vehicle",
        vehicleKey: bookingVehicle.key,
        value: customerProfile.vehicles[0],
      },
    );
    expect(state.vehicles[0]).toMatchObject({
      vehicle_id: "vehicle-1",
      make: "BMW",
      service_id: "full",
      loyalty_reward_id: "reward-1",
      key: bookingVehicle.key,
    });
  });
  it("assigns saved vehicles to their chosen slots without reordering", () => {
    const first = { ...emptyVehicle("basic"), key: "slot-1" };
    const second = { ...emptyVehicle("full"), key: "slot-2" };
    const base = {
      ...initialBookingState,
      customerProfile,
      vehicles: [first, second],
    };
    const withFirst = bookingReducer(base, {
      type: "apply_saved_vehicle",
      vehicleKey: first.key,
      value: customerProfile.vehicles[0],
    });
    const withBoth = bookingReducer(withFirst, {
      type: "apply_saved_vehicle",
      vehicleKey: second.key,
      value: customerProfile.vehicles[1],
    });
    expect(withBoth.vehicles.map((vehicle) => vehicle.key)).toEqual([
      "slot-1",
      "slot-2",
    ]);
    expect(withBoth.vehicles.map((vehicle) => vehicle.vehicle_id)).toEqual([
      "vehicle-1",
      "vehicle-2",
    ]);
    expect(withBoth.vehicles.map((vehicle) => vehicle.service_id)).toEqual([
      "basic",
      "full",
    ]);
  });
  it("prevents assigning the same saved vehicle to two slots", () => {
    const first = { ...emptyVehicle("basic"), key: "slot-1" };
    const second = { ...emptyVehicle("basic"), key: "slot-2" };
    const selected = bookingReducer(
      { ...initialBookingState, vehicles: [first, second] },
      {
        type: "apply_saved_vehicle",
        vehicleKey: first.key,
        value: customerProfile.vehicles[0],
      },
    );
    expect(
      bookingReducer(selected, {
        type: "apply_saved_vehicle",
        vehicleKey: second.key,
        value: customerProfile.vehicles[0],
      }),
    ).toBe(selected);
  });
  it("switches a saved-vehicle slot to manual entry without losing details", () => {
    const selected = {
      ...initialBookingState.vehicles[0],
      vehicle_id: "vehicle-1",
      make: "BMW",
      service_id: "full",
    };
    const state = bookingReducer(
      { ...initialBookingState, vehicles: [selected] },
      { type: "clear_saved_vehicle", vehicleKey: selected.key },
    );
    expect(state.vehicles[0]).toMatchObject({
      vehicle_id: undefined,
      make: "BMW",
      service_id: "full",
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
  it("accepts a blank booking communication email", () => {
    expect(contactErrors({ ...contact, email: "   " }, location).email).toBeUndefined();
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
  it("uses the authoritative vehicle-type price and selected add-ons", () => {
    const pricedCatalogue: Catalogue = {
      ...catalogue,
      services: [
        {
          ...catalogue.services[0],
          prices: [
            { vehicle_type: "sedan", price_minor: 5500 },
            { vehicle_type: "suv", price_minor: 7500 },
          ],
          addons: [
            {
              id: "pet-hair",
              name: "Pet hair removal",
              description: null,
              price_minor: 2000,
              currency_code: "AED",
              default_duration_minutes: 20,
              mobile_available: true,
              shop_available: true,
            },
          ],
        },
      ],
    };
    const vehicle = {
      ...emptyVehicle("basic"),
      vehicle_type: "suv",
      addon_ids: ["pet-hair"],
    };
    expect(calculateEstimate([vehicle], pricedCatalogue)).toBe(9500);
  });
  it("keeps add-ons chargeable when loyalty discounts the base service", () => {
    const pricedCatalogue: Catalogue = {
      ...catalogue,
      services: [
        {
          ...catalogue.services[0],
          prices: [{ vehicle_type: "sedan", price_minor: 5500 }],
          addons: [
            {
              id: "wax",
              name: "Wax",
              description: null,
              price_minor: 1500,
              currency_code: "AED",
              default_duration_minutes: 15,
              mobile_available: true,
              shop_available: true,
            },
          ],
        },
      ],
    };
    const vehicle = {
      ...emptyVehicle("basic"),
      vehicle_type: "sedan",
      addon_ids: ["wax"],
      loyalty_reward_id: "reward-1",
    };
    expect(calculateEstimate([vehicle], pricedCatalogue)).toBe(1500);
  });
  it("toggles add-ons and clears them when the parent service changes", () => {
    const vehicle = { ...emptyVehicle("basic"), addon_ids: [] };
    const selected = bookingReducer(
      { ...initialBookingState, vehicles: [vehicle] },
      { type: "toggle_addon", key: vehicle.key, addonId: "wax" },
    );
    expect(selected.vehicles[0].addon_ids).toEqual(["wax"]);
    const changed = bookingReducer(selected, {
      type: "vehicle",
      key: vehicle.key,
      field: "service_id",
      value: "full",
    });
    expect(changed.vehicles[0].addon_ids).toEqual([]);
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

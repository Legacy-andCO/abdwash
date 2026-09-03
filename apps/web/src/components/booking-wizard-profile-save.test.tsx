// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { CustomerProfileBootstrap } from "@/lib/types";
import { BookingWizard } from "./booking-wizard";

const authState = vi.hoisted(() => ({
  user: null as { id: string } | null,
}));
const api = vi.hoisted(() => ({
  getCatalogue: vi.fn(),
  updateCustomerProfile: vi.fn(),
}));
const profileResource = vi.hoisted(() => ({
  loadCustomerProfile: vi.fn(),
  setCachedCustomerProfile: vi.fn(),
}));

vi.mock("./auth-provider", () => ({
  useAuth: () => ({
    user: authState.user,
    loading: false,
  }),
}));
vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {},
  createBooking: vi.fn(),
  createHold: vi.fn(),
  getAvailability: vi.fn(),
  getCatalogue: (...args: unknown[]) => api.getCatalogue(...args),
  updateCustomerProfile: (...args: unknown[]) =>
    api.updateCustomerProfile(...args),
}));
vi.mock("@/lib/customer-profile-resource", () => ({
  loadCustomerProfile: (...args: unknown[]) =>
    profileResource.loadCustomerProfile(...args),
  setCachedCustomerProfile: (...args: unknown[]) =>
    profileResource.setCachedCustomerProfile(...args),
}));
vi.mock("./location-picker", () => ({
  LocationPicker: ({
    onFieldChange,
    onCoordinatesChange,
  }: {
    onFieldChange: (field: string, value: string) => void;
    onCoordinatesChange: (
      value: { latitude: number; longitude: number },
      writtenAddress?: string,
    ) => void;
  }) => (
    <button
      type="button"
      onClick={() => {
        onFieldChange("instructions", "Gate 2");
        onCoordinatesChange(
          { latitude: 24.49, longitude: 54.4 },
          "Al Reem Island, Abu Dhabi",
        );
      }}
    >
      Fill location
    </button>
  ),
}));
vi.mock("./phone-input", () => ({
  PhoneInput: ({
    value,
    onChange,
  }: {
    value: string;
    onChange: (value: string) => void;
  }) => (
    <label>
      <span>Phone number (WhatsApp number)</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  ),
}));

const catalogue = {
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
      id: "standard",
      name: "Standard Wash",
      description: null,
      price_minor: 5000,
      currency_code: "AED",
      estimated_duration_minutes: 60,
    },
  ],
};

const profile: CustomerProfileBootstrap = {
  authenticated_email: "customer@example.com",
  profile: {
    id: "profile-1",
    first_name: "Ahmad",
    surname: "Awad",
    email: "customer@example.com",
    phone: "+971501234567",
  },
  addresses: [
    {
      id: "address-1",
      label: "Home",
      written_address: "Al Reem Island, Abu Dhabi",
      location_url:
        "https://www.google.com/maps/search/?api=1&query=24.49%2C54.4",
      latitude: 24.49,
      longitude: 54.4,
      location_instructions: "Gate 2",
      is_default: true,
    },
  ],
  vehicles: [
    {
      id: "vehicle-1",
      make: "Toyota",
      model: "Camry",
      year: 2024,
      vehicle_type: "sedan",
      colour: "White",
      plate_number: "A 12345",
      notes: null,
    },
  ],
};

async function continueFromVehiclesToDetails() {
  await userEvent.click(
    await screen.findByRole("button", { name: /Continue/ }),
  );
  await userEvent.click(
    await screen.findByRole("button", { name: /Continue/ }),
  );
  expect(
    await screen.findByRole("heading", { name: "Where should we meet you?" }),
  ).toBeTruthy();
}

beforeEach(() => {
  authState.user = null;
  api.getCatalogue.mockResolvedValue(catalogue);
  profileResource.loadCustomerProfile.mockResolvedValue(profile);
  api.updateCustomerProfile.mockResolvedValue(profile);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("booking profile save on Continue", () => {
  it("saves editable personal information before advancing for a logged-in customer", async () => {
    authState.user = { id: "customer-1" };
    render(<BookingWizard initialServiceId="" />);
    expect((await screen.findByLabelText("Use a saved vehicle") as HTMLSelectElement).value)
      .toBe("vehicle-1");
    expect((screen.getByLabelText("Make") as HTMLInputElement).value).toBe(
      "Toyota",
    );
    await continueFromVehiclesToDetails();

    const firstName = screen.getByLabelText(/First name/);
    await userEvent.clear(firstName);
    await userEvent.type(firstName, "Ahmed");
    await userEvent.click(screen.getByRole("button", { name: /Continue/ }));

    await waitFor(() =>
      expect(api.updateCustomerProfile).toHaveBeenCalledWith({
        first_name: "Ahmed",
        surname: "Awad",
        phone: "+971501234567",
      }),
    );
    expect(profileResource.setCachedCustomerProfile).toHaveBeenCalledWith(
      "customer-1",
      profile,
    );
    expect(
      await screen.findByRole("heading", { name: "When should we come?" }),
    ).toBeTruthy();
  });

  it("does not save a CustomerProfile for a guest", async () => {
    render(<BookingWizard initialServiceId="" />);
    await userEvent.type(await screen.findByLabelText("Make"), "Toyota");
    await userEvent.type(screen.getByLabelText("Model"), "Camry");
    await userEvent.selectOptions(screen.getByLabelText("Vehicle type"), "sedan");
    await userEvent.type(screen.getByLabelText(/Plate number/), "A 12345");
    await continueFromVehiclesToDetails();

    await userEvent.type(screen.getByLabelText(/First name/), "Guest");
    await userEvent.type(screen.getByLabelText(/Surname/), "Customer");
    await userEvent.type(
      screen.getByLabelText(/Email address/),
      "guest@example.com",
    );
    await userEvent.type(
      screen.getByLabelText("Phone number (WhatsApp number)"),
      "+971501234567",
    );
    await userEvent.click(screen.getByRole("button", { name: "Fill location" }));
    await userEvent.click(screen.getByRole("button", { name: /Continue/ }));

    expect(api.updateCustomerProfile).not.toHaveBeenCalled();
    expect(
      await screen.findByRole("heading", { name: "When should we come?" }),
    ).toBeTruthy();
  });

  it("shows an error and blocks progression when profile saving fails", async () => {
    authState.user = { id: "customer-1" };
    api.updateCustomerProfile.mockRejectedValue(new Error("offline"));
    render(<BookingWizard initialServiceId="" />);
    await continueFromVehiclesToDetails();
    await userEvent.click(screen.getByRole("button", { name: /Continue/ }));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "We couldn't save your information",
    );
    expect(
      screen.getByRole("heading", { name: "Where should we meet you?" }),
    ).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "When should we come?" }))
      .toBeNull();
  });
});

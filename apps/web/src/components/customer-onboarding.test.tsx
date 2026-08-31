// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CustomerOnboarding } from "./customer-onboarding";
import { I18nProvider } from "./i18n-provider";
import { resetCustomerProfileResourceForTests } from "@/lib/customer-profile-resource";

const getCustomerProfile = vi.fn();
const updateCustomerProfile = vi.fn();
const createCustomerVehicle = vi.fn();
const authenticatedUser = {
  id: "customer-1",
  email: "verified@example.com",
  user_metadata: {},
};

vi.mock("next/navigation", () => ({ usePathname: () => "/account" }));
vi.mock("./auth-provider", () => ({
  useAuth: () => ({
    user: authenticatedUser,
    loading: false,
    recoveryMode: false,
  }),
}));
vi.mock("@/lib/api", () => ({
  getCustomerProfile: (...args: unknown[]) => getCustomerProfile(...args),
  updateCustomerProfile: (...args: unknown[]) => updateCustomerProfile(...args),
  createCustomerVehicle: (...args: unknown[]) => createCustomerVehicle(...args),
}));

const empty = {
  authenticated_email: "verified@example.com",
  profile: null,
  addresses: [],
  vehicles: [],
};
const complete = {
  ...empty,
  profile: {
    id: "profile-1",
    first_name: "Amina",
    surname: "Ali",
    email: "verified@example.com",
    phone: "+971501234567",
  },
};

beforeEach(() => {
  resetCustomerProfileResourceForTests();
  getCustomerProfile.mockResolvedValue(empty);
  updateCustomerProfile.mockResolvedValue(complete);
  createCustomerVehicle.mockResolvedValue({
    id: "vehicle-1",
    make: "Toyota",
    model: "Camry",
    year: 2024,
    vehicle_type: "sedan",
    colour: null,
    plate_number: "A 12345",
    notes: null,
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("first-login profile onboarding", () => {
  it("shows incomplete profiles and provisions core details before allowing skip", async () => {
    render(<I18nProvider><CustomerOnboarding /></I18nProvider>);
    expect(await screen.findByRole("heading", { name: "Let’s build your profile." })).toBeTruthy();
    expect((screen.getByLabelText(/Email address/) as HTMLInputElement).readOnly).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Save and continue" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Complete all required fields");

    await userEvent.type(screen.getByLabelText("First name"), "Amina");
    await userEvent.type(screen.getByLabelText("Surname"), "Ali");
    await userEvent.type(screen.getByPlaceholderText("50 123 4567"), "0501234567");
    await userEvent.click(screen.getByRole("button", { name: "Save and continue" }));
    await waitFor(() => expect(updateCustomerProfile).toHaveBeenCalledWith({
      first_name: "Amina",
      surname: "Ali",
      phone: "+971501234567",
    }));
    expect(await screen.findByRole("heading", { name: "Add your first vehicle" })).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "I’ll do this later" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("does not appear for a complete server-backed profile", async () => {
    getCustomerProfile.mockResolvedValue(complete);
    render(<I18nProvider><CustomerOnboarding /></I18nProvider>);
    await waitFor(() => expect(getCustomerProfile).toHaveBeenCalledOnce());
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("uses the existing saved-vehicle API", async () => {
    render(<I18nProvider><CustomerOnboarding /></I18nProvider>);
    await userEvent.type(await screen.findByLabelText("First name"), "Amina");
    await userEvent.type(screen.getByLabelText("Surname"), "Ali");
    await userEvent.type(screen.getByPlaceholderText("50 123 4567"), "0501234567");
    await userEvent.click(screen.getByRole("button", { name: "Save and continue" }));
    await userEvent.type(await screen.findByLabelText("Make"), "Toyota");
    await userEvent.type(screen.getByLabelText("Model"), "Camry");
    await userEvent.selectOptions(screen.getByLabelText("Vehicle type"), "sedan");
    await userEvent.type(screen.getByLabelText("Plate number"), "A 12345");
    await userEvent.click(screen.getByRole("button", { name: "Add vehicle" }));
    await waitFor(() => expect(createCustomerVehicle).toHaveBeenCalledWith(expect.objectContaining({
      make: "Toyota",
      vehicle_type: "sedan",
      plate_number: "A 12345",
    })));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("keeps onboarding open and offers retry when loading fails", async () => {
    getCustomerProfile.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(complete);
    render(<I18nProvider><CustomerOnboarding /></I18nProvider>);
    expect((await screen.findByRole("alert")).textContent).toContain("couldn’t load your profile");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(getCustomerProfile).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

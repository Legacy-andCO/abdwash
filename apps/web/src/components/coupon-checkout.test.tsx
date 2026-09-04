// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CouponCheckout } from "./booking-wizard";
import { I18nProvider } from "./i18n-provider";
import * as api from "@/lib/api";
import { initialBookingState } from "@/lib/booking-state";
import type { CouponValidation } from "@/lib/types";

const result = (selected: number | null, lines = [eligibleLine(1)]): CouponValidation => ({
  code: "VIP20",
  discount_percent: 20,
  minimum_vehicle_count: null,
  currency_code: "AED",
  eligible_lines: lines,
  selected_line_position: selected,
  discount_minor: selected ? 1_460 : 0,
});

function eligibleLine(position: number) {
  return {
    position,
    service_id: "standard",
    service_name: "Standard Wash",
    vehicle_type: "sedan",
    make: position === 1 ? "Toyota" : "BMW",
    model: position === 1 ? "Camry" : "X5",
    list_price_minor: 7_300,
    discount_minor: 1_460,
  };
}

function state(coupon: CouponValidation | null = null) {
  return {
    ...initialBookingState,
    coupon,
    catalogue: {
      business_name: "Trifecta",
      settings: {
        timezone: "Asia/Dubai",
        currency_code: "AED",
        opening_time: "09:00",
        closing_time: "21:00",
        slot_duration_minutes: 120,
        multi_vehicle_threshold: 3,
        multi_vehicle_required_slots: 2,
        hold_duration_minutes: 10,
        cancellation_cutoff_hours: 24,
      },
      services: [],
    },
    vehicles: [
      {
        key: "one",
        make: "Toyota",
        model: "Camry",
        year: "2025",
        vehicle_type: "sedan",
        colour: "White",
        plate_number: "A 12345",
        notes: "",
        service_id: "standard",
        addon_ids: [],
      },
    ],
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("coupon checkout", () => {
  it("uppercases input, caps it at six characters, and applies one eligible line", async () => {
    const user = userEvent.setup();
    const dispatch = vi.fn();
    vi.spyOn(api, "validateCoupon").mockResolvedValue(result(1));
    render(
      <I18nProvider>
        <CouponCheckout state={state()} dispatch={dispatch} />
      </I18nProvider>,
    );
    const input = screen.getByLabelText("Coupon code") as HTMLInputElement;
    await user.type(input, "vip20zz");
    expect(input.value).toBe("VIP20Z");
    await user.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() =>
      expect(dispatch).toHaveBeenCalledWith({ type: "coupon", value: result(1) }),
    );
    expect(api.validateCoupon).toHaveBeenCalledWith(
      expect.objectContaining({ code: "VIP20Z" }),
    );
  });

  it("requires a customer choice when several lines are eligible", async () => {
    const user = userEvent.setup();
    const dispatch = vi.fn();
    const lines = [eligibleLine(1), eligibleLine(2)];
    vi.spyOn(api, "validateCoupon")
      .mockResolvedValueOnce(result(null, lines))
      .mockResolvedValueOnce(result(2, lines));
    render(
      <I18nProvider>
        <CouponCheckout state={state()} dispatch={dispatch} />
      </I18nProvider>,
    );
    await user.type(screen.getByLabelText("Coupon code"), "VIP20");
    await user.click(screen.getByRole("button", { name: "Apply" }));
    const choices = await screen.findAllByRole("radio");
    expect(choices).toHaveLength(2);
    await user.click(choices[1]);
    await user.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() =>
      expect(api.validateCoupon).toHaveBeenLastCalledWith(
        expect.objectContaining({ selected_line_position: 2 }),
      ),
    );
    expect(dispatch).toHaveBeenCalledWith({ type: "coupon", value: result(2, lines) });
  });

  it("shows a safe condition error and removes an applied coupon", async () => {
    const user = userEvent.setup();
    const dispatch = vi.fn();
    vi.spyOn(api, "validateCoupon").mockRejectedValue(
      new api.ApiError("COUPON_VEHICLE_INELIGIBLE", "internal", 422),
    );
    const { rerender } = render(
      <I18nProvider>
        <CouponCheckout state={state()} dispatch={dispatch} />
      </I18nProvider>,
    );
    await user.type(screen.getByLabelText("Coupon code"), "VIP20");
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(
      await screen.findByText("This coupon is not valid for this vehicle type."),
    ).toBeTruthy();

    rerender(
      <I18nProvider>
        <CouponCheckout state={state(result(1))} dispatch={dispatch} />
      </I18nProvider>,
    );
    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(dispatch).toHaveBeenCalledWith({ type: "coupon", value: null });
  });
});

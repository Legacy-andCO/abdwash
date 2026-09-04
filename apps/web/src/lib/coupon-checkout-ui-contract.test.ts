import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

describe("coupon checkout UI", () => {
  const wizard = source("../components/booking-wizard.tsx");
  const payment = wizard.slice(
    wizard.indexOf("function PaymentStep"),
    wizard.indexOf("function Confirmation"),
  );
  const checkout = wizard.slice(wizard.indexOf("function CouponCheckout"));

  it("places the compact coupon entry before payment methods", () => {
    expect(payment).toContain("<CouponCheckout");
    expect(payment.indexOf("<CouponCheckout")).toBeLessThan(
      payment.indexOf('className="form-section payment-options"'),
    );
  });

  it("normalizes codes and enforces the six-character limit", () => {
    expect(checkout).toContain('maxLength={6}');
    expect(checkout).toContain('.toUpperCase()');
    expect(checkout).toContain('/[^A-Za-z0-9]/g');
  });

  it("supports one-line auto apply, multi-line selection, removal, and replacement", () => {
    expect(checkout).toContain("result.selected_line_position == null");
    expect(checkout).toContain('name="coupon-line"');
    expect(checkout).toContain('type: "coupon", value: result');
    expect(checkout).toContain('type: "coupon", value: null');
    expect(checkout).toContain("candidate.eligible_lines.map");
  });

  it("shows only backend-confirmed discount values in the final summary", () => {
    expect(payment).toContain("state.coupon.discount_minor");
    expect(payment).toContain("state.coupon?.selected_line_position === index + 1");
    expect(payment).not.toContain("discount_percent / 100");
  });

  it("includes Arabic strings for all coupon outcomes", () => {
    const i18n = source("./i18n.ts");
    expect(i18n).toContain('"booking.coupon.eyebrow": "لديك رمز خصم؟"');
    expect(i18n).toContain('"booking.coupon.vehicle":');
    expect(i18n).toContain('"booking.coupon.loyalty":');
  });
});

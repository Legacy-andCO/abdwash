import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

describe("booking final-step placement", () => {
  const wizard = source("../components/booking-wizard.tsx");
  const details = wizard.slice(
    wizard.indexOf("function DetailsStep"),
    wizard.indexOf("function VehiclesStep"),
  );
  const payment = wizard.slice(
    wizard.indexOf("function PaymentStep"),
    wizard.indexOf("function Confirmation"),
  );

  it("shows collapsed company billing within contact details only", () => {
    expect(details).toContain("<CompanyBillingFields");
    expect(details.indexOf("<CompanyBillingFields")).toBeGreaterThan(
      details.indexOf('t("booking.details.contact")'),
    );
    expect(payment).not.toContain("<CompanyBillingFields");
    expect(wizard).toContain('className="company-billing-disclosure"');
    expect(wizard).toContain('t("booking.details.billingToggle")');
    expect(wizard).toContain("value={state.billing.company_name}");
    expect(wizard).toContain("value={state.billing.tax_registration_number}");
    expect(wizard).toContain("value={state.billing.billing_address}");
  });

  it("shows the Mawaqif notice once between payment options and final actions", () => {
    const home = source("../app/page.tsx");
    expect(home).not.toContain("ServiceAreaNotice");
    expect(details).not.toContain("ServiceAreaNotice");
    expect(wizard.match(/<ServiceAreaNotice compact \/>/g)).toHaveLength(1);
    expect(
      payment.indexOf('className="form-section payment-options"'),
    ).toBeLessThan(payment.indexOf("<ServiceAreaNotice compact />"));
    expect(payment.indexOf("<ServiceAreaNotice compact />")).toBeLessThan(
      payment.lastIndexOf("<StepActions"),
    );
  });

  it("keeps both existing payment choices unchanged", () => {
    expect(payment).toContain('name="payment"');
    expect(payment).toContain('choice === "pay_after_service"');
    expect(payment).toContain('choice === "pay_now"');
    expect(payment).toContain('disabled={choice !== "pay_after_service" || seconds <= 0}');
  });
});

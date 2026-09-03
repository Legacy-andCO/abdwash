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

  it("shows company billing only on the final payment step", () => {
    expect(details).not.toContain('t("booking.details.billing")');
    expect(payment).toContain("<CompanyBillingFields");
    expect(payment.indexOf("<CompanyBillingFields")).toBeLessThan(
      payment.indexOf('className="form-section payment-options"'),
    );
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

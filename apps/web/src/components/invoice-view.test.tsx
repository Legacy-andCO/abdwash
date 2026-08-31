import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = readFileSync(new URL("./invoice-view.tsx", import.meta.url), "utf8");

describe("customer invoice view", () => {
  it("loads through the secure booking token and supports printable HTML", () => {
    expect(source).toContain("getManagedInvoice(token, invoiceId)");
    expect(source).toContain("window.location.hash.slice(1)");
    expect(source).toContain("window.print()");
  });

  it("does not label a non-VAT receipt as a tax invoice", () => {
    expect(source).toContain('invoice.document_type === "tax_invoice"');
    expect(source).toContain('"invoice.standardTitle"');
  });

  it("renders immutable supplier/customer details and discounts", () => {
    expect(source).toContain('snapshotText(invoice.supplier, "legal_name")');
    expect(source).toContain('snapshotText(invoice.customer, "company_name")');
    expect(source).toContain("invoice.discount_minor > 0");
    expect(source).toContain("line.unit_price_minor");
    expect(source).toContain('snapshotText(invoice.supplier, "vat_rate")');
    expect(source).toContain('t("invoice.trn")');
  });
});

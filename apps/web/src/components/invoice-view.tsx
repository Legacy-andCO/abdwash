"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { getManagedInvoice } from "@/lib/api";
import { localizedCustomerError } from "@/lib/customer-error";
import { formatMoney } from "@/lib/dates";
import type { RevenueInvoice } from "@/lib/types";
import { BrandMark } from "./brand-mark";
import { LanguageSwitcher, useI18n } from "./i18n-provider";

function snapshotText(snapshot: Record<string, unknown>, key: string): string {
  const value = snapshot[key];
  return typeof value === "string" ? value : "";
}

export function InvoiceView({ invoiceId }: { invoiceId: string }) {
  const { language, locale, t } = useI18n();
  const [invoice, setInvoice] = useState<RevenueInvoice | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const translationRef = useRef(t);
  const languageRef = useRef(language);
  useEffect(() => {
    translationRef.current = t;
    languageRef.current = language;
  }, [language, t]);
  useEffect(() => {
    const token = decodeURIComponent(window.location.hash.slice(1));
    if (!token || !invoiceId) {
      Promise.resolve().then(() => {
        setError(translationRef.current("invoice.unavailable"));
        setLoading(false);
      });
      return;
    }
    getManagedInvoice(token, invoiceId)
      .then(setInvoice)
      .catch((reason) =>
        setError(
          localizedCustomerError(
            reason,
            languageRef.current,
            translationRef.current,
          ),
        ),
      )
      .finally(() => setLoading(false));
  }, [invoiceId]);

  return (
    <>
      <header className="booking-header no-print">
        <div className="shell">
          <Link className="brand" href="/" aria-label={t("brand.home")}>
            <BrandMark />
          </Link>
          <LanguageSwitcher compact />
        </div>
      </header>
      <main className="invoice-page shell">
        {loading ? <p>{t("invoice.loading")}</p> : null}
        {!loading && !invoice ? (
          <div className="error-banner" role="alert">
            {error || t("invoice.unavailable")}
          </div>
        ) : null}
        {invoice ? (
          <article className="invoice-document">
            <header>
              <BrandMark />
              <div>
                <p>{t("invoice.title")}</p>
                <h1>
                  {t(
                    invoice.document_type === "tax_invoice"
                      ? "invoice.taxTitle"
                      : "invoice.standardTitle",
                  )}
                </h1>
                <strong className="bidi-ltr">{invoice.invoice_number}</strong>
              </div>
            </header>
            <dl className="invoice-meta">
              <dt>{t("invoice.booking")}</dt>
              <dd className="bidi-ltr">{invoice.booking_reference}</dd>
              <dt>{t("invoice.date")}</dt>
              <dd>
                {new Intl.DateTimeFormat(locale, { dateStyle: "long" }).format(
                  new Date(invoice.issued_at),
                )}
              </dd>
              <dt>{t("invoice.paymentMethod")}</dt>
              <dd>{invoice.payment_method.replaceAll("_", " ")}</dd>
            </dl>
            <section className="invoice-parties">
              <div>
                <h2>{t("invoice.supplier")}</h2>
                <strong>
                  {snapshotText(invoice.supplier, "legal_name") ||
                    snapshotText(invoice.supplier, "trading_name")}
                </strong>
                {snapshotText(invoice.supplier, "address") ? (
                  <p>{snapshotText(invoice.supplier, "address")}</p>
                ) : null}
                <p>
                  {[
                    snapshotText(invoice.supplier, "emirate"),
                    snapshotText(invoice.supplier, "country"),
                  ]
                    .filter(Boolean)
                    .join(", ")}
                </p>
                {invoice.document_type === "tax_invoice" &&
                snapshotText(invoice.supplier, "tax_registration_number") ? (
                  <p className="bidi-ltr">
                    {t("invoice.trn")}: {snapshotText(invoice.supplier, "tax_registration_number")}
                  </p>
                ) : null}
              </div>
              <div>
                <h2>{t("invoice.customer")}</h2>
                <strong>
                  {snapshotText(invoice.customer, "company_name") ||
                    snapshotText(invoice.customer, "name")}
                </strong>
                {snapshotText(invoice.customer, "company_name") ? (
                  <p>{snapshotText(invoice.customer, "name")}</p>
                ) : null}
                {snapshotText(invoice.customer, "billing_address") ? (
                  <p>{snapshotText(invoice.customer, "billing_address")}</p>
                ) : null}
                <p className="bidi-ltr">{snapshotText(invoice.customer, "email")}</p>
                {snapshotText(invoice.customer, "tax_registration_number") ? (
                  <p className="bidi-ltr">
                    {t("invoice.trn")}: {snapshotText(invoice.customer, "tax_registration_number")}
                  </p>
                ) : null}
              </div>
            </section>
            <div className="invoice-lines-table">
              <table>
                <thead>
                  <tr>
                    <th>{t("invoice.description")}</th>
                    <th>{t("invoice.quantity")}</th>
                    <th>{t("invoice.unitPrice")}</th>
                    <th>{t("invoice.discount")}</th>
                    <th>{t("invoice.amount")}</th>
                  </tr>
                </thead>
                <tbody>
                  {invoice.lines.map((line, index) => (
                    <tr key={`${line.description}-${index}`}>
                      <td>
                        <strong>{line.description}</strong>
                        {line.vehicle ? <small>{line.vehicle}</small> : null}
                      </td>
                      <td>{line.quantity}</td>
                      <td>
                        {formatMoney(
                          line.unit_price_minor,
                          invoice.currency_code,
                          locale,
                        )}
                      </td>
                      <td>
                        {formatMoney(
                          line.discount_minor,
                          invoice.currency_code,
                          locale,
                        )}
                      </td>
                      <td>
                        {formatMoney(
                          line.line_total_minor,
                          invoice.currency_code,
                          locale,
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <dl className="invoice-totals">
              <dt>{t("invoice.subtotal")}</dt>
              <dd>
                {formatMoney(invoice.subtotal_minor, invoice.currency_code, locale)}
              </dd>
              {invoice.discount_minor > 0 ? (
                <>
                  <dt>{t("invoice.discount")}</dt>
                  <dd>
                    −{formatMoney(invoice.discount_minor, invoice.currency_code, locale)}
                  </dd>
                </>
              ) : null}
              {invoice.document_type === "tax_invoice" ? (
                <>
                  <dt>
                    {t("invoice.vat")} ({snapshotText(invoice.supplier, "vat_rate") || "0"}%)
                  </dt>
                  <dd>
                    {formatMoney(
                      invoice.vat_amount_minor,
                      invoice.currency_code,
                      locale,
                    )}
                  </dd>
                </>
              ) : null}
              <dt>{t("invoice.total")}</dt>
              <dd>
                <strong>
                  {formatMoney(invoice.total_minor, invoice.currency_code, locale)}
                </strong>
              </dd>
            </dl>
            <button
              className="button no-print"
              type="button"
              onClick={() => window.print()}
            >
              {t("invoice.print")}
            </button>
          </article>
        ) : null}
      </main>
    </>
  );
}

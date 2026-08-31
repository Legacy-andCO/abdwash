"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getCatalogue } from "@/lib/api";
import { localizedCustomerError } from "@/lib/customer-error";
import { formatMoney } from "@/lib/dates";
import {
  localizeServiceDescription,
  localizeServiceFeature,
  localizeServiceName,
} from "@/lib/i18n";
import type { Catalogue, Service } from "@/lib/types";
import { useI18n } from "./i18n-provider";

type PricingClass = "car" | "suv";

function priceFor(service: Service, pricingClass: PricingClass): number {
  const vehicleType = pricingClass === "car" ? "sedan" : "suv";
  return (
    service.prices?.find((price) => price.vehicle_type === vehicleType)
      ?.price_minor ?? service.price_minor
  );
}

export function serviceFeatureAdditions(
  service: Service,
  previous?: Service,
): string[] {
  const previousFeatures = new Set(previous?.included_features ?? []);
  return (service.included_features ?? []).filter(
    (feature) => !previousFeatures.has(feature),
  );
}

export function ServicesPreview() {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pricingClass, setPricingClass] = useState<PricingClass>("car");
  const { language, locale, t } = useI18n();
  useEffect(() => {
    getCatalogue().then(setCatalogue).catch(setError);
  }, []);
  const core = useMemo(
    () =>
      catalogue?.services.filter((service) =>
        ["Standard Wash", "Gold Wash", "Premium Wash"].includes(service.name),
      ) ?? [],
    [catalogue],
  );
  const featureRows = useMemo(
    () => [...new Set(core.flatMap((service) => service.included_features ?? []))],
    [core],
  );
  const secondary =
    catalogue?.services.filter(
      (service) =>
        !["Standard Wash", "Gold Wash", "Premium Wash"].includes(service.name),
    ) ?? [];

  if (!catalogue && !error) {
    return (
      <div className="service-grid" aria-label={t("services.loading")}>
        {[0, 1, 2].map((item) => (
          <div className="service-card skeleton" key={item} aria-hidden="true" />
        ))}
      </div>
    );
  }
  if (error != null) {
    return (
      <div className="inline-notice service-error" role="alert">
        <strong>{t("services.wait")}</strong>
        <span>{localizedCustomerError(error, language, t)}</span>
      </div>
    );
  }
  return (
    <div className="catalogue-showcase">
      <div
        className="pricing-class-toggle"
        role="group"
        aria-label={t("services.comparison")}
      >
        {(["car", "suv"] as const).map((value) => (
          <button
            type="button"
            key={value}
            className={pricingClass === value ? "selected" : ""}
            aria-pressed={pricingClass === value}
            onClick={() => setPricingClass(value)}
          >
            {t(value === "car" ? "services.car" : "services.suv")}
          </button>
        ))}
      </div>
      <div className="service-comparison-scroll service-comparison-desktop">
        <table className="service-comparison">
          <caption>{t("services.comparison")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("services.included")}</th>
              {core.map((service) => (
                <th scope="col" key={service.id}>
                  <strong>{localizeServiceName(language, service.name)}</strong>
                  <span>
                    {formatMoney(
                      priceFor(service, pricingClass),
                      service.currency_code,
                      locale,
                    )}
                  </span>
                  <Link href={`/book?service=${service.id}`}>
                    {t("services.choose")}
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {featureRows.map((feature) => (
              <tr key={feature}>
                <th scope="row">{localizeServiceFeature(language, feature)}</th>
                {core.map((service) => {
                  const included = (service.included_features ?? []).includes(feature);
                  return (
                    <td
                      key={service.id}
                      aria-label={included ? "Included" : "Not included"}
                    >
                      {included ? "✓" : "—"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="service-comparison-mobile">
        {core.map((service, index) => {
          const previous = core[index - 1];
          const additions = serviceFeatureAdditions(service, previous);
          return (
            <article className="mobile-comparison-card" key={service.id}>
              <header>
                <h3>{localizeServiceName(language, service.name)}</h3>
                <strong>
                  {formatMoney(
                    priceFor(service, pricingClass),
                    service.currency_code,
                    locale,
                  )}
                </strong>
              </header>
              <p>
                {previous
                  ? t("services.everythingPrevious", {
                      service: localizeServiceName(language, previous.name),
                    })
                  : t("services.regularCare")}
              </p>
              <ul className="service-feature-list">
                {additions.map((feature) => (
                  <li key={feature}>✓ {localizeServiceFeature(language, feature)}</li>
                ))}
              </ul>
              <details>
                <summary>{t("services.viewAllFeatures")}</summary>
                <ul className="service-feature-list">
                  {(service.included_features ?? []).map((feature) => (
                    <li key={feature}>✓ {localizeServiceFeature(language, feature)}</li>
                  ))}
                </ul>
              </details>
              <Link className="button" href={`/book?service=${service.id}`}>
                {t("services.choose")}
              </Link>
            </article>
          );
        })}
      </div>
      <h3 className="secondary-services-title">{t("services.otherCare")}</h3>
      <div className="service-grid secondary-services">
        {secondary.map((service, index) => (
          <article className="service-card" key={service.id}>
            <div
              className={`service-visual wash-${(index % 3) + 1}`}
              aria-hidden="true"
            >
              <span>{String(index + 4).padStart(2, "0")}</span>
            </div>
            <div className="service-card-body">
              <div className="service-title-row">
                <h3>{localizeServiceName(language, service.name)}</h3>
                <span>
                  {formatMoney(
                    priceFor(service, pricingClass),
                    service.currency_code,
                    locale,
                  )}
                </span>
              </div>
              <p>
                {localizeServiceDescription(
                  language,
                  service.description,
                  "services.defaultDescription",
                )}
              </p>
              <ul className="service-feature-list">
                {(service.included_features ?? []).map((feature) => (
                  <li key={feature}>✓ {localizeServiceFeature(language, feature)}</li>
                ))}
              </ul>
              <div className="service-meta">
                <span>
                  ≈ {t("services.minutes", { minutes: service.estimated_duration_minutes })}
                </span>
                {service.customer_bookable !== false ? (
                  <Link href={`/book?service=${service.id}`}>
                    {t("services.choose")} <span className="directional-icon" aria-hidden="true">→</span>
                  </Link>
                ) : (
                  <span>{t("services.packageUnavailable")}</span>
                )}
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

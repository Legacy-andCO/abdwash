"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getCatalogue } from "@/lib/api";
import { localizedCustomerError } from "@/lib/customer-error";
import { formatMoney } from "@/lib/dates";
import type { Catalogue } from "@/lib/types";
import { useI18n } from "./i18n-provider";
import { localizeServiceDescription, localizeServiceName } from "@/lib/i18n";

export function ServicesPreview() {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [error, setError] = useState<unknown>(null);
  const { language, locale, t } = useI18n();
  useEffect(() => { getCatalogue().then(setCatalogue).catch(setError); }, []);
  return <div className="service-grid" aria-live="polite">{!catalogue && !error && [0, 1, 2].map((item) => <div className="service-card skeleton" key={item} aria-hidden="true" />)}{error != null && <div className="inline-notice service-error"><strong>{t("services.wait")}</strong><span>{localizedCustomerError(error, language, t)}</span></div>}{catalogue?.services.slice(0, 3).map((service, index) => <article className="service-card" key={service.id}><div className={`service-visual wash-${(index % 3) + 1}`} aria-hidden="true"><span>{String(index + 1).padStart(2, "0")}</span></div><div className="service-card-body"><div className="service-title-row"><h3>{localizeServiceName(language, service.name)}</h3><span>{t("services.from")} {formatMoney(service.price_minor, service.currency_code, locale)}</span></div><p>{localizeServiceDescription(language, service.description, "services.defaultDescription")}</p><div className="service-meta"><span>≈ {t("services.minutes", { minutes: service.estimated_duration_minutes })}</span><Link href={`/book?service=${service.id}`}>{t("services.choose")} <span className="directional-icon" aria-hidden="true">→</span></Link></div></div></article>)}</div>;
}

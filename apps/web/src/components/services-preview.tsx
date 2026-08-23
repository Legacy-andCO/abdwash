"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { friendlyError, getCatalogue } from "@/lib/api";
import { formatMoney } from "@/lib/dates";
import type { Catalogue } from "@/lib/types";

export function ServicesPreview() {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { getCatalogue().then(setCatalogue).catch((reason) => setError(friendlyError(reason))); }, []);
  return <div className="service-grid" aria-live="polite">{!catalogue && !error && [0, 1, 2].map((item) => <div className="service-card skeleton" key={item} aria-hidden="true" />)}{error && <div className="inline-notice service-error"><strong>Services are taking a moment.</strong><span>{error}</span></div>}{catalogue?.services.slice(0, 3).map((service, index) => <article className="service-card" key={service.id}><div className={`service-visual wash-${(index % 3) + 1}`} aria-hidden="true"><span>{String(index + 1).padStart(2, "0")}</span></div><div className="service-card-body"><div className="service-title-row"><h3>{service.name}</h3><span>From {formatMoney(service.price_minor, service.currency_code)}</span></div><p>{service.description ?? "A thorough mobile wash delivered at a place that works for you."}</p><div className="service-meta"><span>≈ {service.estimated_duration_minutes} min</span><Link href={`/book?service=${service.id}`}>Choose service <span aria-hidden="true">→</span></Link></div></div></article>)}</div>;
}

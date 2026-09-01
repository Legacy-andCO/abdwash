"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getPublicReviewSummary } from "@/lib/api";
import type { PublicReviewSummary } from "@/lib/types";
import { useI18n } from "./i18n-provider";
import { ReviewCard } from "./review-card";

export function HomeReviews() {
  const { t } = useI18n();
  const [summary, setSummary] = useState<PublicReviewSummary | null>(null);
  useEffect(() => {
    let active = true;
    void getPublicReviewSummary().then((value) => { if (active) setSummary(value); }).catch(() => undefined);
    return () => { active = false; };
  }, []);
  if (!summary) return null;
  return <section className="section home-reviews">
    <div className="shell">
      <div className="section-heading"><div><p className="eyebrow"><span /> {t("reviews.lovedBy")}</p><h2>{t("reviews.whatCustomersSay")}</h2></div>
        <div className="review-summary"><strong>{summary.average_rating ? `★ ${summary.average_rating.toFixed(1)}` : "—"}</strong><span>{t("reviews.basedOn", { count: summary.total_count })}</span></div>
      </div>
      {summary.featured_reviews.length ? <div className="review-card-grid">{summary.featured_reviews.map((review) => <ReviewCard key={review.id} review={review} />)}</div> : <p className="review-empty">{t("reviews.empty")}</p>}
      <div className="review-section-actions"><Link className="button button-ghost" href="/reviews">{t("reviews.seeAll")}</Link><Link className="text-link" href="/reviews/leave">{t("reviews.reviewUs")}</Link></div>
    </div>
  </section>;
}

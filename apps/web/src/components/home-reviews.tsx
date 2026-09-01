"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getPublicReviewSummary, hideReview } from "@/lib/api";
import type { PublicReviewSummary } from "@/lib/types";
import { useI18n } from "./i18n-provider";
import { ReviewCard } from "./review-card";
import { ScrollReveal } from "./scroll-reveal";
import { useReviewModerationAccess } from "./use-review-moderation";

export function HomeReviews() {
  const { t } = useI18n();
  const [summary, setSummary] = useState<PublicReviewSummary | null>(null);
  const canModerate = useReviewModerationAccess();
  useEffect(() => {
    let active = true;
    void getPublicReviewSummary().then((value) => { if (active) setSummary(value); }).catch(() => undefined);
    return () => { active = false; };
  }, []);
  async function removeReview(reviewId: string) {
    await hideReview(reviewId);
    setSummary(await getPublicReviewSummary());
  }
  if (!summary) return null;
  return <ScrollReveal as="section" className="section home-reviews">
    <div className="shell">
      <div className="section-heading"><div><p className="eyebrow"><span /> {t("reviews.lovedBy")}</p><h2>{t("reviews.whatCustomersSay")}</h2></div>
        <div className="review-summary"><strong>{summary.average_rating ? `★ ${summary.average_rating.toFixed(1)}` : "—"}</strong><span>{t("reviews.basedOn", { count: summary.total_count })}</span></div>
      </div>
      {summary.featured_reviews.length ? <ScrollReveal className="review-card-grid" stagger>{summary.featured_reviews.map((review) => <ReviewCard key={review.id} review={review} canModerate={canModerate} onRemove={removeReview} />)}</ScrollReveal> : <p className="review-empty">{t("reviews.empty")}</p>}
      <div className="review-section-actions"><Link className="button button-ghost" href="/reviews">{t("reviews.seeAll")}</Link><Link className="text-link" href="/reviews/leave">{t("reviews.reviewUs")}</Link></div>
    </div>
  </ScrollReveal>;
}

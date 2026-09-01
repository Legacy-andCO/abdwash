"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getPublicReviews, hideReview } from "@/lib/api";
import type { PublicReviewList } from "@/lib/types";
import { ReviewCard } from "./review-card";
import { SiteFooter } from "./site-footer";
import { SiteHeader } from "./site-header";
import { useI18n } from "./i18n-provider";
import { ScrollReveal } from "./scroll-reveal";
import { useReviewModerationAccess } from "./use-review-moderation";

export function ReviewsPage() {
  const { t } = useI18n();
  const [data, setData] = useState<PublicReviewList | null>(null);
  const [error, setError] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const canModerate = useReviewModerationAccess();
  useEffect(() => {
    let active = true;
    void getPublicReviews().then((value) => { if (active) setData(value); }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, []);
  async function loadMore() {
    if (!data || loadingMore || data.reviews.length >= data.total_count) return;
    setLoadingMore(true);
    setError(false);
    try {
      const next = await getPublicReviews(20, data.reviews.length);
      setData({ ...next, reviews: [...data.reviews, ...next.reviews] });
    } catch {
      setError(true);
    } finally {
      setLoadingMore(false);
    }
  }
  async function removeReview(reviewId: string) {
    await hideReview(reviewId);
    setData(await getPublicReviews());
  }
  return <><SiteHeader /><main className="reviews-page"><section className="shell reviews-hero">
    <p className="eyebrow"><span /> {t("reviews.eyebrow")}</p><h1>{t("reviews.pageTitle")}</h1>
    {data && <div className="review-summary large"><strong>{data.average_rating ? `★ ${data.average_rating.toFixed(1)}` : "—"}</strong><span>{t("reviews.basedOn", { count: data.total_count })}</span></div>}
    <Link className="button" href="/reviews/leave">{t("reviews.reviewUs")}</Link>
  </section><ScrollReveal as="section" className="section shell">
    {!data && !error && <div className="loading-panel" role="status"><span className="spinner dark" /><strong>{t("common.loading")}</strong></div>}
    {error && <div className="error-banner" role="alert">{t("reviews.loadFailed")}</div>}
    {data && (data.reviews.length ? <ScrollReveal className="review-card-grid full" stagger>{data.reviews.map((review) => <ReviewCard key={review.id} review={review} canModerate={canModerate} onRemove={removeReview} />)}</ScrollReveal> : <p className="review-empty">{t("reviews.empty")}</p>)}
    {data && data.reviews.length < data.total_count && <div className="review-section-actions"><button className="button button-ghost" type="button" disabled={loadingMore} onClick={() => void loadMore()}>{loadingMore ? t("common.loading") : t("reviews.loadMore")}</button></div>}
  </ScrollReveal></main><SiteFooter /></>;
}

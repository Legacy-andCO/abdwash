"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getPublicReviews } from "@/lib/api";
import type { PublicReviewList } from "@/lib/types";
import { ReviewCard } from "./review-card";
import { SiteFooter } from "./site-footer";
import { SiteHeader } from "./site-header";
import { useI18n } from "./i18n-provider";

export function ReviewsPage() {
  const { t } = useI18n();
  const [data, setData] = useState<PublicReviewList | null>(null);
  const [error, setError] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
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
  return <><SiteHeader /><main className="reviews-page"><section className="shell reviews-hero">
    <p className="eyebrow"><span /> {t("reviews.eyebrow")}</p><h1>{t("reviews.pageTitle")}</h1>
    {data && <div className="review-summary large"><strong>{data.average_rating ? `★ ${data.average_rating.toFixed(1)}` : "—"}</strong><span>{t("reviews.basedOn", { count: data.total_count })}</span></div>}
    <Link className="button" href="/reviews/leave">{t("reviews.reviewUs")}</Link>
  </section><section className="section shell">
    {!data && !error && <div className="loading-panel" role="status"><span className="spinner dark" /><strong>{t("common.loading")}</strong></div>}
    {error && <div className="error-banner" role="alert">{t("reviews.loadFailed")}</div>}
    {data && (data.reviews.length ? <div className="review-card-grid full">{data.reviews.map((review) => <ReviewCard key={review.id} review={review} />)}</div> : <p className="review-empty">{t("reviews.empty")}</p>)}
    {data && data.reviews.length < data.total_count && <div className="review-section-actions"><button className="button button-ghost" type="button" disabled={loadingMore} onClick={() => void loadMore()}>{loadingMore ? t("common.loading") : t("reviews.loadMore")}</button></div>}
  </section></main><SiteFooter /></>;
}

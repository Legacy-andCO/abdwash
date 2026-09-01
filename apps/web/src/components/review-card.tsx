"use client";

import type { PublicReview } from "@/lib/types";
import { localizeServiceName } from "@/lib/i18n";
import { useI18n } from "./i18n-provider";

export function ReviewCard({ review }: { review: PublicReview }) {
  const { language, locale, t } = useI18n();
  return <article className="public-review-card">
    <div className="review-stars" aria-label={t("reviews.ratingOutOfFive", { rating: review.rating })}>{"★".repeat(review.rating)}{"☆".repeat(5 - review.rating)}</div>
    {review.comment && <blockquote>“{review.comment}”</blockquote>}
    <footer><strong>{review.reviewer_display_name}</strong><span>{t("reviews.verifiedCustomer")}</span><small>{localizeServiceName(language, review.service_name)} · {new Date(review.service_date).toLocaleDateString(locale, { month: "long", year: "numeric" })}</small></footer>
  </article>;
}

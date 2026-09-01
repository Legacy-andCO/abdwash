"use client";

import { useState } from "react";
import type { PublicReview, ReviewEligibility } from "@/lib/types";
import { useI18n } from "./i18n-provider";

export function ReviewForm({
  eligibility,
  compact = false,
  onSubmit,
  onClose,
}: {
  eligibility: ReviewEligibility;
  compact?: boolean;
  onSubmit: (rating: number, comment: string) => Promise<PublicReview>;
  onClose?: () => void;
}) {
  const { locale, t } = useI18n();
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState<PublicReview | null>(null);
  const existing = submitted ?? eligibility.existing_review;

  if (existing) {
    return <div className="review-success" role="status">
      <div className="review-stars" aria-label={t("reviews.ratingOutOfFive", { rating: existing.rating })}>
        {"★".repeat(existing.rating)}{"☆".repeat(5 - existing.rating)}
      </div>
      <strong>{submitted ? t("reviews.thanks") : t("reviews.yourReview")}</strong>
      {existing.comment && <p>{existing.comment}</p>}
      {onClose && <button className="button button-ghost" type="button" onClick={onClose}>{t("common.close")}</button>}
    </div>;
  }

  async function submit() {
    if (!rating || busy) {
      setError(t("reviews.ratingRequired"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      setSubmitted(await onSubmit(rating, comment));
    } catch {
      setError(t("reviews.submitFailed"));
    } finally {
      setBusy(false);
    }
  }

  return <div className={compact ? "review-form compact" : "review-form"}>
    <p className="eyebrow"><span /> {t("reviews.howWasService")}</p>
    <h2>{t("reviews.reviewUs")}</h2>
    {eligibility.booking_reference && <p className="review-booking-label">
      {eligibility.service_name} · <bdi>{eligibility.booking_reference}</bdi>
      {eligibility.service_date ? ` · ${new Date(eligibility.service_date).toLocaleDateString(locale, { dateStyle: "medium" })}` : ""}
    </p>}
    <div className="review-star-input" role="radiogroup" aria-label={t("reviews.chooseRating")}>
      {[1, 2, 3, 4, 5].map((value) => <button
        key={value}
        type="button"
        role="radio"
        aria-checked={rating === value}
        aria-label={t("reviews.starRating", { rating: value })}
        className={value <= rating ? "selected" : ""}
        onClick={() => setRating(value)}
      >★</button>)}
    </div>
    <label>
      <span>{t("reviews.tellUsMore")} <em>{t("common.optional")}</em></span>
      <textarea rows={compact ? 3 : 5} maxLength={1000} value={comment} onChange={(event) => setComment(event.target.value)} />
      <small>{comment.length}/1000</small>
    </label>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <div className="review-actions">
      <button className="button" type="button" disabled={busy} onClick={() => void submit()}>{busy ? t("common.saving") : t("reviews.submit")}</button>
      {onClose && <button className="auth-switch" type="button" disabled={busy} onClick={onClose}>{t("reviews.maybeLater")}</button>}
    </div>
  </div>;
}

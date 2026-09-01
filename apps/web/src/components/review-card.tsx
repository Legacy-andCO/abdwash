"use client";

import { useState } from "react";
import type { PublicReview } from "@/lib/types";
import { localizeServiceName } from "@/lib/i18n";
import { useI18n } from "./i18n-provider";

export function ReviewCard({
  review,
  canModerate = false,
  onRemove,
}: {
  review: PublicReview;
  canModerate?: boolean;
  onRemove?: (reviewId: string) => Promise<void>;
}) {
  const { language, locale, t } = useI18n();
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function removeReview() {
    if (!onRemove || busy) return;
    setBusy(true);
    setError("");
    try {
      await onRemove(review.id);
    } catch {
      setError(t("reviews.removeFailed"));
      setBusy(false);
    }
  }

  return <article className="public-review-card">
    {canModerate && onRemove ? <div className="review-moderation">
      <button className="review-menu-button" type="button" aria-label={t("reviews.actions")} aria-expanded={menuOpen} onClick={() => setMenuOpen((value) => !value)}>⋮</button>
      {menuOpen && !confirming ? <div className="review-menu"><button type="button" onClick={() => setConfirming(true)}>{t("reviews.removeReview")}</button></div> : null}
      {confirming ? <div className="review-remove-confirm" role="dialog" aria-label={t("reviews.removeConfirm")}>
        <strong>{t("reviews.removeConfirm")}</strong>
        <p>{t("reviews.removeCopy")}</p>
        {error ? <span className="field-error" role="alert">{error}</span> : null}
        <div><button type="button" disabled={busy} onClick={() => { setConfirming(false); setMenuOpen(false); }}>{t("common.cancel")}</button><button type="button" disabled={busy} onClick={() => void removeReview()}>{busy ? t("common.saving") : t("common.remove")}</button></div>
      </div> : null}
    </div> : null}
    <div className="review-stars" aria-label={t("reviews.ratingOutOfFive", { rating: review.rating })}>{"★".repeat(review.rating)}{"☆".repeat(5 - review.rating)}</div>
    {review.comment && <blockquote>“{review.comment}”</blockquote>}
    <footer><strong>{review.reviewer_display_name}</strong><span>{t("reviews.verifiedCustomer")}</span><small>{localizeServiceName(language, review.service_name)} · {new Date(review.service_date).toLocaleDateString(locale, { month: "long", year: "numeric" })}</small></footer>
  </article>;
}

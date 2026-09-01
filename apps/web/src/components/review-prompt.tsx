"use client";

import { useEffect, useState } from "react";
import { recordCustomerReviewOpen, submitCustomerReview } from "@/lib/api";
import type { ReviewEligibility } from "@/lib/types";
import { useAuth } from "./auth-provider";
import { useI18n } from "./i18n-provider";
import { ReviewForm } from "./review-form";

export function ReviewPrompt() {
  const { t } = useI18n();
  const { user, loading } = useAuth();
  const userId = user?.id ?? null;
  const [eligibility, setEligibility] = useState<ReviewEligibility | null>(null);

  useEffect(() => {
    if (loading || !userId) return;
    const key = `trifecta-review-open:${userId}`;
    if (window.sessionStorage.getItem(key) === "1") return;
    window.sessionStorage.setItem(key, "1");
    let active = true;
    void recordCustomerReviewOpen()
      .then((result) => {
        if (active && result.show_prompt) setEligibility(result.eligibility);
      })
      .catch(() => undefined);
    return () => { active = false; };
  }, [loading, userId]);

  if (!eligibility?.eligible || !eligibility.booking_id) return null;
  return <div className="review-prompt-backdrop" onMouseDown={(event) => {
    if (event.currentTarget === event.target) setEligibility(null);
  }}>
    <section className="review-prompt" role="dialog" aria-modal="true" aria-labelledby="review-prompt-title">
      <button className="review-close" type="button" aria-label={t("common.close")} onClick={() => setEligibility(null)}>×</button>
      <div id="review-prompt-title">
        <ReviewForm
          eligibility={eligibility}
          compact
          onClose={() => setEligibility(null)}
          onSubmit={(rating, comment) => submitCustomerReview({ booking_id: eligibility.booking_id!, rating, comment })}
        />
      </div>
    </section>
  </div>;
}

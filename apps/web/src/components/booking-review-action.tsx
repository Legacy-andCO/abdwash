"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  getCustomerBookingReviewEligibility,
  getManagedReviewEligibility,
} from "@/lib/api";
import type { ReviewEligibility } from "@/lib/types";
import { useI18n } from "./i18n-provider";

export function BookingReviewAction({
  bookingId,
  managementToken,
}: {
  bookingId?: string;
  managementToken?: string;
}) {
  const { t } = useI18n();
  const [eligibility, setEligibility] = useState<ReviewEligibility | null>(null);
  useEffect(() => {
    const request = bookingId
      ? getCustomerBookingReviewEligibility(bookingId)
      : managementToken
        ? getManagedReviewEligibility(managementToken)
        : null;
    if (!request) return;
    let active = true;
    void request.then((value) => { if (active) setEligibility(value); }).catch(() => undefined);
    return () => { active = false; };
  }, [bookingId, managementToken]);
  if (!eligibility) return null;
  if (eligibility.existing_review) return <section className="booking-review-summary">
    <h2>{t("reviews.yourReview")}</h2><div className="review-stars">{"★".repeat(eligibility.existing_review.rating)}{"☆".repeat(5 - eligibility.existing_review.rating)}</div>{eligibility.existing_review.comment && <p>{eligibility.existing_review.comment}</p>}
  </section>;
  if (!eligibility.eligible) return null;
  const href = bookingId
    ? `/reviews/leave?booking=${encodeURIComponent(bookingId)}`
    : `/reviews/leave#${encodeURIComponent(managementToken ?? "")}`;
  return <section className="booking-review-summary"><h2>{t("reviews.howWasService")}</h2><p>{t("reviews.leaveReviewCopy")}</p><Link className="button" href={href}>{t("reviews.leaveReview")}</Link></section>;
}

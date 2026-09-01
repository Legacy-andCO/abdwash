"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  getCustomerBookingReviewEligibility,
  getCustomerReviewEligibility,
  getManagedReviewEligibility,
  submitCustomerReview,
  submitGuestReview,
  verifyGuestReview,
} from "@/lib/api";
import { getGuestDeviceId } from "@/lib/guest-device";
import type { TranslationKey } from "@/lib/i18n";
import type { ReviewEligibility } from "@/lib/types";
import { useAuth } from "./auth-provider";
import { ReviewForm } from "./review-form";
import { SiteFooter } from "./site-footer";
import { SiteHeader } from "./site-header";
import { useI18n } from "./i18n-provider";

export function LeaveReviewPage() {
  const { t } = useI18n();
  const { user, loading: authLoading } = useAuth();
  const userId = user?.id ?? null;
  const searchParams = useSearchParams();
  const bookingId = searchParams.get("booking");
  const [managementToken, setManagementToken] = useState("");
  const reviewToken = useRef("");
  const deviceId = useRef("");
  const [eligibility, setEligibility] = useState<ReviewEligibility | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<TranslationKey | "">("");
  const [reference, setReference] = useState("");
  const [phone, setPhone] = useState("");

  useEffect(() => {
    if (authLoading) return;
    deviceId.current = getGuestDeviceId();
    const currentManagementToken = decodeURIComponent(window.location.hash.slice(1));
    const tokenTimer = window.setTimeout(
      () => setManagementToken(currentManagementToken),
      0,
    );
    let active = true;
    const request = userId
      ? bookingId
        ? getCustomerBookingReviewEligibility(bookingId)
        : getCustomerReviewEligibility()
      : currentManagementToken
        ? getManagedReviewEligibility(currentManagementToken)
        : null;
    if (!request) {
      const loadingTimer = window.setTimeout(() => setLoading(false), 0);
      return () => {
        window.clearTimeout(tokenTimer);
        window.clearTimeout(loadingTimer);
      };
    }
    void request.then((value) => { if (active) setEligibility(value); }).catch(() => { if (active) setError("reviews.eligibilityFailed"); }).finally(() => { if (active) setLoading(false); });
    return () => {
      active = false;
      window.clearTimeout(tokenTimer);
    };
  }, [authLoading, bookingId, userId]);

  async function verify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true); setError("");
    try {
      const result = await verifyGuestReview({ booking_reference: reference, phone, device_id: deviceId.current });
      reviewToken.current = result.review_token;
      setEligibility(result.eligibility);
    } catch {
      setError("reviews.verificationFailed");
    } finally { setLoading(false); }
  }

  return <><SiteHeader /><main className="reviews-page leave-review-page"><section className="shell review-leave-card">
    {loading && <div className="loading-panel" role="status"><span className="spinner dark" /><strong>{t("common.loading")}</strong></div>}
    {!loading && eligibility && (eligibility.eligible || eligibility.existing_review) && <ReviewForm eligibility={eligibility} onSubmit={(rating, comment) => {
      if (userId && eligibility.booking_id) return submitCustomerReview({ booking_id: eligibility.booking_id, rating, comment });
      return submitGuestReview({ review_token: reviewToken.current || undefined, management_token: managementToken || undefined, device_id: deviceId.current, rating, comment });
    }} />}
    {!loading && eligibility && !eligibility.eligible && !eligibility.existing_review && <div className="review-empty"><h1>{t("reviews.noneEligibleTitle")}</h1><p>{t("reviews.noneEligible")}</p></div>}
    {!loading && !userId && !managementToken && !eligibility && <form className="review-verify-form" onSubmit={(event) => void verify(event)}>
      <p className="eyebrow"><span /> {t("reviews.reviewUs")}</p><h1>{t("reviews.verifyTitle")}</h1><p>{t("reviews.verifyCopy")}</p>
      <label><span>{t("reviews.bookingReference")}</span><input className="bidi-ltr" required maxLength={20} value={reference} onChange={(event) => setReference(event.target.value)} /></label>
      <label><span>{t("booking.details.phone")}</span><input className="bidi-ltr" required inputMode="tel" value={phone} onChange={(event) => setPhone(event.target.value)} /></label>
      <button className="button" type="submit">{t("reviews.verify")}</button>
    </form>}
    {error && <div className="error-banner" role="alert">{t(error)}</div>}
  </section></main><SiteFooter /></>;
}

"use client";

import Link from "next/link";
import { policyTitles, type PolicySlug } from "@/lib/policies";
import { useI18n } from "./i18n-provider";

export function BookingPolicyAcceptance({
  checked,
  disabled,
  onChange,
}: {
  checked: boolean;
  disabled: boolean;
  onChange: (checked: boolean) => void;
}) {
  const { language } = useI18n();
  const ar = language === "ar";
  const link = (slug: PolicySlug) => (
    <Link href={`/${slug}`} target="_blank" rel="noopener">{policyTitles[slug][language]}</Link>
  );
  return (
    <div className="policy-checkbox">
      <input
        id="booking-policy-acceptance"
        type="checkbox"
        required
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        aria-labelledby="booking-policy-acceptance-text"
      />
      <span id="booking-policy-acceptance-text">
        <label htmlFor="booking-policy-acceptance">
          {ar ? "قرأتُ وأوافق على" : "I have read and agree to the"}
        </label>{" "}
        {link("terms-and-conditions")}{ar ? " و" : " and "}
        {link("cancellation-and-refund-policy")}
        {ar ? "، وأقرّ بالاطلاع على " : ", and I acknowledge the "}
        {link("privacy-policy")}.
      </span>
    </div>
  );
}

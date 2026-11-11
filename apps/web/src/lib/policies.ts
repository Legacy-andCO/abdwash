export const POLICY_REVISION = "2026-11-10.2";
export const POLICY_LAST_UPDATED = "2026-11-10";
// Set to the approved effective date as part of the publication release.
export const POLICY_EFFECTIVE_DATE: string | null = null;
export const CONTACT_EMAIL = "contact@trifecta-wash.com";
export const CONTACT_PHONE = "+971 56 420 4954";
export const CONTACT_TEL = "tel:+971564204954";

export const policyTitles = {
  "terms-and-conditions": {
    "en": "Terms & Conditions",
    "ar": "الشروط والأحكام"
  },
  "cancellation-and-refund-policy": {
    "en": "Cancellation & Refund Policy",
    "ar": "سياسة الإلغاء والاسترداد"
  },
  "service-warranty-and-aftercare": {
    "en": "Service Warranty & Aftercare Policy",
    "ar": "سياسة ضمان الخدمة والعناية اللاحقة"
  },
  "privacy-policy": {
    "en": "Privacy Policy",
    "ar": "سياسة الخصوصية"
  },
  "data-protection": {
    "en": "Data Protection & Confidentiality Policy",
    "ar": "سياسة حماية البيانات والسرية"
  },
  "complaints": {
    "en": "Customer Complaints Procedure",
    "ar": "إجراءات شكاوى العملاء"
  }
} as const;

export type PolicySlug = keyof typeof policyTitles;
export const policySlugs = Object.keys(policyTitles) as PolicySlug[];

export function policyMetadata(slug: PolicySlug) {
  return { title: policyTitles[slug].en, robots: { index: false, follow: true } };
}

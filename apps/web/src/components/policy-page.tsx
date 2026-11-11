"use client";

import Link from "next/link";
import { ComplaintForm } from "./complaint-form";
import { useI18n } from "./i18n-provider";
import { SiteFooter } from "./site-footer";
import { SiteHeader } from "./site-header";
import arabicContent from "@/lib/policies.ar.json";
import englishContent from "@/lib/policies.en.json";
import {
  CONTACT_EMAIL,
  CONTACT_PHONE,
  CONTACT_TEL,
  POLICY_EFFECTIVE_DATE,
  POLICY_LAST_UPDATED,
  POLICY_REVISION,
  policySlugs,
  policyTitles,
  type PolicySlug,
} from "@/lib/policies";

export function PolicyPage({ slug }: { slug: PolicySlug }) {
  const { language, direction } = useI18n();
  const ar = language === "ar";
  const title = policyTitles[slug][language];
  const content = (ar ? arabicContent : englishContent)[slug];
  return (
    <>
      <SiteHeader />
      <main className="subpage" lang={language} dir={direction}>
        <article className="shell narrow-card policy-page">
          <p className="eyebrow">
            {ar ? "تريفيكتا لغسل وتلميع السيارات" : "Trifecta Car Washing & Polishing"}
          </p>
          <h1>{title}</h1>
          <dl className="policy-metadata">
            <dt>{ar ? "تاريخ النفاذ" : "Effective date"}</dt>
            <dd>{POLICY_EFFECTIVE_DATE
              ? <time dateTime={POLICY_EFFECTIVE_DATE}>{POLICY_EFFECTIVE_DATE}</time>
              : ar ? "لم يُحدَّد بعد" : "Pending publication approval"}</dd>
            <dt>{ar ? "آخر تحديث" : "Last updated"}</dt>
            <dd><time dateTime={POLICY_LAST_UPDATED}>{POLICY_LAST_UPDATED}</time></dd>
            <dt>{ar ? "إصدار السياسة" : "Policy version"}</dt>
            <dd><bdi>{POLICY_REVISION}</bdi></dd>
          </dl>
          {slug === "complaints" && (
            <a className="button" href="#complaint-form">
              {ar ? "انتقل إلى نموذج الشكوى" : "Go to the complaint form"}
            </a>
          )}
          {content.map(([heading, body], index) => (
            <section key={heading}>
              <h2>{heading}</h2>
              <p>{body}</p>
              {slug === "complaints" && index === 5 && (
                <p className="policy-links">
                  <a href="tel:800555" dir="ltr">800555</a>
                  <a href="mailto:contact@tamm.abudhabi" dir="ltr">contact@tamm.abudhabi</a>
                  <a href="https://adra.gov.ae/en/Compliance-and-Regulations/consumer-protection">
                    {ar ? "حماية المستهلك في أبوظبي" : "Abu Dhabi consumer protection"}
                  </a>
                </p>
              )}
            </section>
          ))}
          <section>
            <h2>{ar ? "التواصل مع تريفيكتا" : "Contact Trifecta"}</h2>
            <p>{ar ? "أبوظبي، الإمارات العربية المتحدة" : "Abu Dhabi, United Arab Emirates"}</p>
            <p className="policy-links">
              <a href={`mailto:${CONTACT_EMAIL}`} dir="ltr">{CONTACT_EMAIL}</a>
              <a href={CONTACT_TEL} dir="ltr">{CONTACT_PHONE}</a>
            </p>
          </section>
          {slug === "complaints" && <ComplaintForm />}
          <nav aria-label={ar ? "سياسات أخرى" : "Related policies"} className="policy-links">
            {policySlugs.filter((policy) => policy !== slug).map((policy) => (
              <Link key={policy} href={`/${policy}`}>{policyTitles[policy][language]}</Link>
            ))}
          </nav>
        </article>
      </main>
      <SiteFooter />
    </>
  );
}

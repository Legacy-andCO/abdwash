"use client";

import Link from "next/link";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { useI18n } from "@/components/i18n-provider";
import { CONTACT_EMAIL, CONTACT_PHONE, CONTACT_TEL, policyTitles } from "@/lib/policies";

export default function ContactPage() {
  const { language, t } = useI18n();
  return (
    <>
      <SiteHeader />
      <main className="subpage">
        <section className="shell narrow-card contact-card">
          <p className="eyebrow"><span /> {t("nav.contact")}</p>
          <h1>{t("contact.title")}</h1>
          <p>{t("contact.copy")}</p>
          <div className="contact-details">
            <a href={CONTACT_TEL}><span>{t("contact.call")}</span><strong dir="ltr">{CONTACT_PHONE}</strong></a>
            <a href="https://wa.me/971564204954" target="_blank" rel="noopener noreferrer">
              <span>{t("contact.phone")}</span><strong dir="ltr">{CONTACT_PHONE}</strong>
            </a>
            <a href={`mailto:${CONTACT_EMAIL}`}>
              <span>{t("contact.email")}</span><strong dir="ltr">{CONTACT_EMAIL}</strong>
            </a>
            <div><span>{t("contact.coverageLabel")}</span><strong>{t("contact.coverage")}</strong></div>
          </div>
          <div className="contact-actions">
            <Link className="button" href="/book">{t("contact.personalEnquiry")}</Link>
            <a className="button button-ghost" href={`mailto:${CONTACT_EMAIL}?subject=Corporate%20%2F%20Property%20enquiry`}>
              {t("contact.corporateEnquiry")}
            </a>
          </div>
          <p className="policy-links"><Link href="/complaints">{policyTitles.complaints[language]}</Link></p>
          <small>{t("contact.responseNote")}</small>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

"use client";

import Link from "next/link";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { useI18n } from "@/components/i18n-provider";

export default function ContactPage() {
  const { t } = useI18n();
  return <><SiteHeader /><main className="subpage"><section className="shell narrow-card contact-card"><p className="eyebrow"><span /> {t("nav.contact")}</p><h1>{t("contact.title")}</h1><p>{t("contact.copy")}</p><div className="contact-details"><a href="https://wa.me/971564204954" target="_blank" rel="noopener noreferrer"><span>{t("contact.phone")}</span><strong dir="ltr">+971 56 420 4954</strong></a><a href="mailto:contact@trifecta-wash.com"><span>{t("contact.email")}</span><strong dir="ltr">contact@trifecta-wash.com</strong></a><div><span>{t("contact.coverageLabel")}</span><strong>{t("contact.coverage")}</strong></div></div><div className="contact-actions"><Link className="button" href="/book">{t("contact.personalEnquiry")}</Link><a className="button button-ghost" href="mailto:contact@trifecta-wash.com?subject=Corporate%20%2F%20Property%20enquiry">{t("contact.corporateEnquiry")}</a></div><small>{t("contact.responseNote")}</small></section></main><SiteFooter /></>;
}

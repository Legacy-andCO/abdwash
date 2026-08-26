"use client";
import Link from "next/link";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { useI18n } from "@/components/i18n-provider";
export default function ContactPage() { const { t } = useI18n(); return <><SiteHeader /><main className="subpage"><section className="shell narrow-card"><p className="eyebrow"><span /> {t("nav.contact")}</p><h1>{t("contact.title")}</h1><p>{t("contact.copy")}</p><div className="contact-placeholder"><span>{t("contact.care")}</span><strong>{t("contact.preparing")}</strong><small>{t("contact.privacy")}</small></div><Link className="button" href="/book">{t("nav.book")} <span className="directional-icon" aria-hidden="true">→</span></Link></section></main><SiteFooter /></>; }

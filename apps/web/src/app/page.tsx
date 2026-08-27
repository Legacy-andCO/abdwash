"use client";
import Link from "next/link";
import Image from "next/image";
import { ServicesPreview } from "@/components/services-preview";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { HomeBookingStatus } from "@/components/home-booking-status";
import { HomeLoyaltyStatus } from "@/components/home-loyalty-status";
import { useI18n } from "@/components/i18n-provider";

export default function HomePage() {
  const { t } = useI18n();
  const benefits = [
    ["01", t("home.benefit1Title"), t("home.benefit1Copy")],
    ["02", t("home.benefit2Title"), t("home.benefit2Copy")],
    ["03", t("home.benefit3Title"), t("home.benefit3Copy")],
  ];
  return (
    <><SiteHeader /><main><HomeBookingStatus />
      <section className="hero"><div className="shell hero-grid">
        <div className="hero-copy"><p className="eyebrow"><span /> {t("home.eyebrow")}</p><h1>{t("home.title")} <em>{t("home.titleAccent")}</em></h1><p className="hero-lead">{t("home.lead")}</p><div className="hero-actions"><Link className="button" href="/book">{t("home.book")} <span className="directional-icon" aria-hidden="true">→</span></Link><a className="text-link" href="#services">{t("home.explore")} <span aria-hidden="true">↓</span></a></div><div className="trust-row" aria-label={t("home.servicesTitle")}><span>✓ {t("home.mobile")}</span><span>✓ {t("home.secure")}</span><span>✓ {t("home.payAfter")}</span></div></div>
        <div className="hero-art" aria-label={t("home.artLabel")}><Image className="hero-brand-logo" src="/brand/trifecta-emblem.png" alt="" width={223} height={223} priority /><div className="hero-stat"><span>{t("home.schedule")}</span><strong dir="ltr">09:00—21:00</strong><small>{t("home.daily")}</small></div></div>
      </div><div className="shell benefit-strip">{benefits.map(([number, title, copy]) => <div key={number}><span>{number}</span><p><strong>{title}</strong>{copy}</p></div>)}</div></section>
      <HomeLoyaltyStatus />
      <section className="section shell" id="services"><div className="section-heading"><div><p className="eyebrow"><span /> {t("nav.services")}</p><h2>{t("home.servicesTitle")}</h2></div><p>{t("home.servicesCopy")}</p></div><ServicesPreview /></section>
      <section className="promo-section"><div className="shell promo-card"><div className="promo-visual" aria-hidden="true"><div className="promo-bubble">{t("home.extraCare")}</div><div className="promo-shine">✦</div></div><div className="promo-copy"><p className="eyebrow light"><span /> {t("home.seasonal")}</p><h2>{t("home.promoTitle")}</h2><p>{t("home.promoCopy")}</p><Link className="button button-light" href="/book">{t("home.findService")} <span className="directional-icon" aria-hidden="true">→</span></Link></div></div></section>
      <section className="section shell" id="how-it-works"><div className="center-heading"><p className="eyebrow"><span /> {t("nav.how")}</p><h2>{t("home.howTitle")}</h2></div><div className="steps-grid"><article><span className="step-icon">01</span><h3>{t("home.step1Title")}</h3><p>{t("home.step1Copy")}</p></article><article><span className="step-icon">02</span><h3>{t("home.step2Title")}</h3><p>{t("home.step2Copy")}</p></article><article><span className="step-icon">03</span><h3>{t("home.step3Title")}</h3><p>{t("home.step3Copy")}</p></article></div></section>
      <section className="section shell testimonial-placeholder" aria-label={t("home.promise")}><p>“{t("home.promise")}”</p><span>{t("home.standard")}</span></section>
      <section className="final-cta"><div className="shell"><p className="eyebrow light"><span /> {t("home.ready")}</p><h2>{t("home.ctaTitle")}</h2><p>{t("home.ctaCopy")}</p><Link className="button button-light" href="/book">{t("home.start")} <span className="directional-icon" aria-hidden="true">→</span></Link></div></section>
    </main><SiteFooter /></>
  );
}

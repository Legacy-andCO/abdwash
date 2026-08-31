"use client";

import Link from "next/link";
import { SiteFooter } from "./site-footer";
import { SiteHeader } from "./site-header";
import { useI18n } from "./i18n-provider";

const capabilities = [
  "about.capabilityWash",
  "about.capabilityInterior",
  "about.capabilityPolishing",
  "about.capabilityVip",
  "about.capabilityEngine",
  "about.capabilityHeadlights",
  "about.capabilitySteam",
] as const;

const reasons = [
  "about.reasonMobile",
  "about.reasonProducts",
  "about.reasonVip",
  "about.reasonTeam",
  "about.reasonContact",
] as const;

export function AboutPage() {
  const { t } = useI18n();
  return <><SiteHeader /><main className="about-page">
    <section className="about-hero"><div className="shell about-hero-grid"><div><p className="eyebrow light"><span /> {t("about.positioning")}</p><h1>{t("about.title")}</h1><p>{t("about.intro")}</p><div className="about-hero-actions"><Link className="button" href="/book">{t("about.bookService")}</Link><a className="text-link" href="#who-we-serve">{t("about.discover")}</a></div></div><div className="about-signature" aria-label={t("brand.tagline")}><span>{t("about.brandLine")}</span><strong>{t("brand.tagline")}</strong><small>{t("about.coverageShort")}</small></div></div></section>

    <section className="section shell about-story"><div className="section-heading"><div><p className="eyebrow"><span /> {t("nav.about")}</p><h2>{t("about.storyTitle")}</h2></div><p>{t("about.storyCopy")}</p></div><div className="about-values"><article><span>{t("about.missionLabel")}</span><h3>{t("about.missionTitle")}</h3><p>{t("about.mission")}</p></article><article><span>{t("about.visionLabel")}</span><h3>{t("about.visionTitle")}</h3><p>{t("about.vision")}</p></article></div></section>

    <section className="about-founders"><div className="shell"><div className="section-heading"><div><p className="eyebrow"><span /> {t("about.foundersLabel")}</p><h2>{t("about.foundersTitle")}</h2></div><p>{t("about.foundersCopy")}</p></div><div className="founder-grid"><article><span>AA</span><h3>Abdallah Awad</h3><p>{t("about.coFounder")}</p></article><article><span>FA</span><h3>Faisal Alateibi</h3><p>{t("about.coFounder")}</p></article></div></div></section>

    <section className="section shell" id="who-we-serve"><div className="center-heading"><p className="eyebrow"><span /> {t("about.serveLabel")}</p><h2>{t("about.serveTitle")}</h2></div><div className="audience-grid"><article><span>{t("about.b2cTag")}</span><h3>{t("about.individuals")}</h3><p>{t("about.individualsCopy")}</p><Link className="button" href="/book">{t("about.bookService")}</Link></article><article className="corporate-card"><span>{t("about.b2bTag")}</span><h3>{t("about.businesses")}</h3><p>{t("about.businessesCopy")}</p><Link className="button button-light" href="/contact?enquiry=corporate">{t("about.corporateEnquiry")}</Link></article></div></section>

    <section className="about-capabilities"><div className="shell"><div className="section-heading"><div><p className="eyebrow light"><span /> {t("about.capabilitiesLabel")}</p><h2>{t("about.capabilitiesTitle")}</h2></div><p>{t("about.capabilitiesCopy")}</p></div><div className="capability-grid">{capabilities.map((key) => <span key={key}>{t(key)}</span>)}</div><small>{t("about.capabilitiesNote")}</small></div></section>

    <section className="section shell"><div className="center-heading"><p className="eyebrow"><span /> {t("about.processLabel")}</p><h2>{t("about.processTitle")}</h2></div><div className="corporate-steps"><article><span>01</span><h3>{t("about.process1Title")}</h3><p>{t("about.process1Copy")}</p></article><article><span>02</span><h3>{t("about.process2Title")}</h3><p>{t("about.process2Copy")}</p></article><article><span>03</span><h3>{t("about.process3Title")}</h3><p>{t("about.process3Copy")}</p></article><article><span>04</span><h3>{t("about.process4Title")}</h3><p>{t("about.process4Copy")}</p></article></div></section>

    <section className="about-why"><div className="shell about-why-grid"><div><p className="eyebrow"><span /> {t("about.whyLabel")}</p><h2>{t("about.whyTitle")}</h2><p>{t("about.coverage")}</p></div><div className="reason-list">{reasons.map((key) => <p key={key}><span aria-hidden="true">✓</span>{t(key)}</p>)}</div></div></section>

    <section className="about-closing"><div className="shell"><p className="eyebrow light"><span /> {t("about.togetherLabel")}</p><h2>{t("about.togetherTitle")}</h2><p>{t("about.togetherCopy")}</p><div className="about-closing-actions"><Link className="button button-light" href="/contact?enquiry=corporate">{t("about.contactTrifecta")}</Link><a className="text-link light-link" href="/company/Trifecta_Car_Washing_Company_Profile.pdf" download>{t("about.downloadProfile")}</a></div></div></section>
  </main><SiteFooter /></>;
}

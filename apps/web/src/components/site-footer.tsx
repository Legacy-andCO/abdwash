"use client";
import Link from "next/link";
import { CONTACT_EMAIL, CONTACT_PHONE, CONTACT_TEL, policySlugs, policyTitles } from "@/lib/policies";
import { BrandMark } from "./brand-mark";
import { useI18n } from "./i18n-provider";

export function SiteFooter() {
  const { language, t } = useI18n();
  return (
    <footer className="site-footer">
      <div className="shell footer-grid">
        <div>
          <Link className="brand brand-footer" href="/" aria-label={t("brand.home")}><BrandMark light /></Link>
          <p>{t("footer.description")}</p>
        </div>
        <div>
          <p className="footer-label">{t("footer.explore")}</p>
          <Link href="/#services">{t("nav.services")}</Link>
          <Link href="/#how-it-works">{t("nav.how")}</Link>
          <Link href="/about">{t("nav.about")}</Link>
          <Link href="/reviews">{t("reviews.pageLink")}</Link>
          <Link href="/reviews/leave">{t("reviews.reviewUs")}</Link>
          <Link href="/book">{t("footer.bookNow")}</Link>
        </div>
        <div>
          <p className="footer-label">{t("footer.support")}</p>
          <Link href="/contact">{t("nav.contact")}</Link>
          <a href={CONTACT_TEL}><bdi>{CONTACT_PHONE}</bdi></a>
          <a href={`mailto:${CONTACT_EMAIL}`}><bdi>{CONTACT_EMAIL}</bdi></a>
          <span>{t("footer.location")}</span>
        </div>
        <div>
          <p className="footer-label">{t("footer.policies")}</p>
          {policySlugs.map((slug) => (
            <Link key={slug} href={`/${slug}`}>{policyTitles[slug][language]}</Link>
          ))}
        </div>
      </div>
      <div className="shell footer-bottom">
        <span>{t("footer.copyright", { year: new Date().getFullYear() })}</span>
        <span>{t("footer.promise")}</span>
      </div>
    </footer>
  );
}

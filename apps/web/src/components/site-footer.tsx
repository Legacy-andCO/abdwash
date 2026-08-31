"use client";
import Link from "next/link";
import { BrandMark } from "./brand-mark";
import { useI18n } from "./i18n-provider";

export function SiteFooter() {
  const { t } = useI18n();
  return <footer className="site-footer"><div className="shell footer-grid"><div><Link className="brand brand-footer" href="/" aria-label={t("brand.home")}><BrandMark light /></Link><p>{t("footer.description")}</p></div><div><p className="footer-label">{t("footer.explore")}</p><Link href="/#services">{t("nav.services")}</Link><Link href="/#how-it-works">{t("nav.how")}</Link><Link href="/about">{t("nav.about")}</Link><Link href="/book">{t("footer.bookNow")}</Link></div><div><p className="footer-label">{t("footer.support")}</p><Link href="/contact">{t("nav.contact")}</Link><a href="tel:+971564204954" dir="ltr">+971 56 420 4954</a><span>{t("footer.location")}</span></div></div><div className="shell footer-bottom"><span>{t("footer.copyright", { year: new Date().getFullYear() })}</span><span>{t("footer.promise")}</span></div></footer>;
}

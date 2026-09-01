"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  cachedCustomerProfile,
  loadCustomerProfile,
} from "@/lib/customer-profile-resource";
import { useAuth } from "./auth-provider";
import { BrandMark } from "./brand-mark";
import { LanguageSwitcher, useI18n } from "./i18n-provider";

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const [logoutError, setLogoutError] = useState("");
  const pathname = usePathname();
  const { user, loading, logout } = useAuth();
  const { t } = useI18n();
  const [profileName, setProfileName] = useState<{
    userId: string;
    firstName: string;
  } | null>(null);
  const cachedName = user
    ? cachedCustomerProfile(user.id)?.profile?.first_name.trim() ?? ""
    : "";
  const metadataName =
    typeof user?.user_metadata.first_name === "string"
      ? user.user_metadata.first_name.trim()
      : "";
  const firstName =
    user && profileName?.userId === user.id
      ? profileName.firstName || metadataName
      : cachedName || metadataName;
  const loginHref = `/login?returnTo=${encodeURIComponent(pathname)}`;

  useEffect(() => {
    if (!user) return;
    let active = true;
    const load = (refresh = false) => {
      void loadCustomerProfile(user.id, { refresh })
        .then((data) => {
          if (active)
            setProfileName({
              userId: user.id,
              firstName: data.profile?.first_name.trim() ?? "",
            });
        })
        .catch(() => undefined);
    };
    load();
    const refreshProfile = () => load(true);
    window.addEventListener("trifecta-loyalty-updated", refreshProfile);
    return () => {
      active = false;
      window.removeEventListener("trifecta-loyalty-updated", refreshProfile);
    };
  }, [user]);

  async function handleLogout() {
    setLogoutError("");
    try {
      await logout();
      setOpen(false);
    } catch {
      setLogoutError(t("nav.logoutError"));
    }
  }

  return <header className="site-header"><div className="shell header-inner">
    <Link className="brand" href="/" aria-label={t("brand.home")}><BrandMark /></Link>
    <button className="menu-button" type="button" aria-expanded={open} aria-controls="primary-navigation" onClick={() => setOpen((value) => !value)}><span className="sr-only">{t("nav.toggle")}</span><span /><span /></button>
    <nav id="primary-navigation" className={open ? "nav-links is-open" : "nav-links"} aria-label={t("nav.primary")}>
      <Link href="/#services" onClick={() => setOpen(false)}>{t("nav.services")}</Link>
      <Link href="/#how-it-works" onClick={() => setOpen(false)}>{t("nav.how")}</Link>
      <Link href="/about" onClick={() => setOpen(false)}>{t("nav.about")}</Link>
      <Link href="/contact" onClick={() => setOpen(false)}>{t("nav.contact")}</Link>
      {!loading && !user && <Link href={loginHref} onClick={() => setOpen(false)}>{t("nav.login")}</Link>}
      {!loading && user && <div className="account-links"><Link href="/account" onClick={() => setOpen(false)}>{firstName ? t("nav.hello", { name: firstName }) : t("nav.account")}</Link><button type="button" onClick={() => void handleLogout()}>{t("nav.logout")}</button></div>}
      <LanguageSwitcher compact />
      <Link className="button button-small" href="/book" onClick={() => setOpen(false)}>{t("nav.book")}</Link>
    </nav>
    {logoutError && <span className="header-auth-error" role="alert">{logoutError}</span>}
  </div></header>;
}

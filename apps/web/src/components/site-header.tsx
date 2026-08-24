"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAuth } from "./auth-provider";
import { BrandMark } from "./brand-mark";

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const [logoutError, setLogoutError] = useState("");
  const pathname = usePathname();
  const { user, loading, logout } = useAuth();
  const firstName = typeof user?.user_metadata.first_name === "string" ? user.user_metadata.first_name : "";
  const loginHref = `/login?returnTo=${encodeURIComponent(pathname)}`;

  async function handleLogout() {
    setLogoutError("");
    try {
      await logout();
      setOpen(false);
    } catch {
      setLogoutError("We couldn't log you out. Please try again.");
    }
  }

  return <header className="site-header"><div className="shell header-inner">
    <Link className="brand" href="/" aria-label="AbdWash home"><BrandMark /><span>AbdWash</span></Link>
    <button className="menu-button" type="button" aria-expanded={open} aria-controls="primary-navigation" onClick={() => setOpen((value) => !value)}><span className="sr-only">Toggle navigation</span><span /><span /></button>
    <nav id="primary-navigation" className={open ? "nav-links is-open" : "nav-links"} aria-label="Primary navigation">
      <Link href="/#services" onClick={() => setOpen(false)}>Services</Link>
      <Link href="/#how-it-works" onClick={() => setOpen(false)}>How it works</Link>
      <Link href="/contact" onClick={() => setOpen(false)}>Contact</Link>
      {!loading && !user && <Link href={loginHref} onClick={() => setOpen(false)}>Log in</Link>}
      {!loading && user && <div className="account-links"><Link href="/account" onClick={() => setOpen(false)}>{firstName ? `Hi, ${firstName}` : "Account"}</Link><button type="button" onClick={() => void handleLogout()}>Log out</button></div>}
      <Link className="button button-small" href="/book" onClick={() => setOpen(false)}>Book a wash</Link>
    </nav>
    {logoutError && <span className="header-auth-error" role="alert">{logoutError}</span>}
  </div></header>;
}

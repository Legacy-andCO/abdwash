"use client";
import Link from "next/link";
import { useState } from "react";
import { BrandMark } from "./brand-mark";

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  return <header className="site-header"><div className="shell header-inner"><Link className="brand" href="/" aria-label="AbdWash home"><BrandMark /><span>AbdWash</span></Link><button className="menu-button" type="button" aria-expanded={open} aria-controls="primary-navigation" onClick={() => setOpen((value) => !value)}><span className="sr-only">Toggle navigation</span><span /><span /></button><nav id="primary-navigation" className={open ? "nav-links is-open" : "nav-links"} aria-label="Primary navigation"><Link href="/#services" onClick={() => setOpen(false)}>Services</Link><Link href="/#how-it-works" onClick={() => setOpen(false)}>How it works</Link><Link href="/contact" onClick={() => setOpen(false)}>Contact</Link><span className="login-placeholder" title="Customer accounts are coming soon">Log in <span>soon</span></span><Link className="button button-small" href="/book" onClick={() => setOpen(false)}>Book a wash</Link></nav></div></header>;
}

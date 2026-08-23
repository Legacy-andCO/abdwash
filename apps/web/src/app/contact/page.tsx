import type { Metadata } from "next";
import Link from "next/link";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
export const metadata: Metadata = { title: "Contact" };
export default function ContactPage() { return <><SiteHeader /><main className="subpage"><section className="shell narrow-card"><p className="eyebrow"><span /> Contact</p><h1>We’d love to help.</h1><p>Our full support centre is coming soon. For a new wash, the fastest route is the booking flow.</p><div className="contact-placeholder"><span>Customer care</span><strong>Support details are being prepared.</strong><small>No contact form data is collected on this page.</small></div><Link className="button" href="/book">Book a wash <span aria-hidden="true">→</span></Link></section></main><SiteFooter /></>; }

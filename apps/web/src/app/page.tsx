import Link from "next/link";
import { ServicesPreview } from "@/components/services-preview";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { HomeBookingStatus } from "@/components/home-booking-status";

const benefits = [
  ["01", "We come to you", "Home, work, or wherever your car is parked."],
  ["02", "Clear, fair pricing", "Choose the right service before you confirm."],
  ["03", "Built around your day", "Real availability, reserved as you book."],
];

export default function HomePage() {
  return (
    <><SiteHeader /><main><HomeBookingStatus />
      <section className="hero"><div className="shell hero-grid">
        <div className="hero-copy"><p className="eyebrow"><span /> Mobile car care in Abu Dhabi</p><h1>Your car, cared for. <em>Wherever you are.</em></h1><p className="hero-lead">Professional car washing brought to your home or workplace. Simple booking, honest pricing, and a finish you’ll notice.</p><div className="hero-actions"><Link className="button" href="/book">Book your wash <span aria-hidden="true">→</span></Link><a className="text-link" href="#services">Explore services <span aria-hidden="true">↓</span></a></div><div className="trust-row" aria-label="Service highlights"><span>✓ Mobile service</span><span>✓ Secure booking</span><span>✓ Pay after service</span></div></div>
        <div className="hero-art" aria-label="A clean car represented by a calm water-inspired illustration"><div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" /><div className="car-silhouette"><div className="car-roof" /><div className="car-body" /><i /><i /></div><div className="hero-stat"><span>Care, on your schedule</span><strong>09:00—21:00</strong><small>Daily availability</small></div><span className="sparkle sparkle-one">✦</span><span className="sparkle sparkle-two">✦</span></div>
      </div><div className="shell benefit-strip">{benefits.map(([number, title, copy]) => <div key={number}><span>{number}</span><p><strong>{title}</strong>{copy}</p></div>)}</div></section>
      <section className="section shell" id="services"><div className="section-heading"><div><p className="eyebrow"><span /> Services</p><h2>Every wash, done properly.</h2></div><p>Choose the care your car needs. We’ll bring the equipment, attention, and finish to you.</p></div><ServicesPreview /></section>
      <section className="promo-section"><div className="shell promo-card"><div className="promo-visual" aria-hidden="true"><div className="promo-bubble">A little extra care</div><div className="promo-shine">✦</div></div><div className="promo-copy"><p className="eyebrow light"><span /> Seasonal care</p><h2>Fresh car. Clear head.</h2><p>Our next care package is being prepared. For now, every service is delivered with the same thoughtful attention.</p><Link className="button button-light" href="/book">Find your service <span aria-hidden="true">→</span></Link></div></div></section>
      <section className="section shell" id="how-it-works"><div className="center-heading"><p className="eyebrow"><span /> How it works</p><h2>Clean car, three simple steps.</h2></div><div className="steps-grid"><article><span className="step-icon">01</span><h3>Tell us what you need</h3><p>Pick a service and add the cars you’d like us to care for.</p></article><article><span className="step-icon">02</span><h3>Choose a real time</h3><p>See live availability and reserve the window that fits your day.</p></article><article><span className="step-icon">03</span><h3>We come to you</h3><p>Our mobile team arrives at your chosen location, ready to work.</p></article></div></section>
      <section className="section shell testimonial-placeholder" aria-label="Customer promise"><p>“The kind of clean that makes every drive feel better.”</p><span>THE ABDWASH STANDARD</span></section>
      <section className="final-cta"><div className="shell"><p className="eyebrow light"><span /> Ready when you are</p><h2>Give your car the care it deserves.</h2><p>Choose your service, location, and time in just a few minutes.</p><Link className="button button-light" href="/book">Start your booking <span aria-hidden="true">→</span></Link></div></section>
    </main><SiteFooter /></>
  );
}

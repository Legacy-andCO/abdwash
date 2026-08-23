import Link from "next/link";
import { BrandMark } from "./brand-mark";

export function SiteFooter() {
  return <footer className="site-footer"><div className="shell footer-grid"><div><Link className="brand brand-footer" href="/"><BrandMark /><span>AbdWash</span></Link><p>Professional mobile car care, wherever your day takes you.</p></div><div><p className="footer-label">Explore</p><Link href="/#services">Services</Link><Link href="/#how-it-works">How it works</Link><Link href="/book">Book now</Link></div><div><p className="footer-label">Support</p><Link href="/contact">Contact</Link><span>Dubai, UAE</span></div></div><div className="shell footer-bottom"><span>© {new Date().getFullYear()} AbdWash</span><span>Care that comes to you.</span></div></footer>;
}

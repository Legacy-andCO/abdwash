import { Suspense } from "react";
import { LoginForm } from "@/components/login-form";
import { SiteHeader } from "@/components/site-header";

export default function LoginPage() {
  return <><SiteHeader /><main className="auth-page"><Suspense fallback={<div className="auth-card loading-panel"><span className="spinner dark" /><strong>Preparing login…</strong></div>}><LoginForm /></Suspense></main></>;
}

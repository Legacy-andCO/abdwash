"use client";
import { Suspense } from "react";
import { LoginForm } from "@/components/login-form";
import { SiteHeader } from "@/components/site-header";
import { useI18n } from "@/components/i18n-provider";

export default function LoginPage() {
  const { t } = useI18n();
  return <><SiteHeader /><main className="auth-page"><Suspense fallback={<div className="auth-card loading-panel"><span className="spinner dark" /><strong>{t("auth.preparing")}</strong></div>}><LoginForm /></Suspense></main></>;
}

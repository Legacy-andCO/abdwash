import type { Metadata } from "next";
import { ForgotPasswordForm } from "@/components/forgot-password-form";
import { SiteHeader } from "@/components/site-header";

export const metadata: Metadata = {
  title: "Forgot password",
  robots: { index: false, follow: false },
};

export default function ForgotPasswordPage() {
  return <><SiteHeader /><main className="auth-page"><ForgotPasswordForm /></main></>;
}

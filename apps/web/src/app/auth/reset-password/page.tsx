import type { Metadata } from "next";
import { ResetPasswordForm } from "@/components/reset-password-form";
import { SiteHeader } from "@/components/site-header";

export const metadata: Metadata = {
  title: "Reset password",
  robots: { index: false, follow: false },
};

export default function ResetPasswordPage() {
  return <><SiteHeader /><main className="auth-page"><ResetPasswordForm /></main></>;
}

"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useAuth } from "./auth-provider";
import { useI18n } from "./i18n-provider";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function ForgotPasswordForm() {
  const { t } = useI18n();
  const { available, requestPasswordReset } = useAuth();
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state === "loading") return;
    setError("");
    if (!EMAIL_PATTERN.test(email.trim())) {
      setState("error");
      setError(t("auth.resetEmailInvalid"));
      return;
    }
    setState("loading");
    try {
      await requestPasswordReset(email.trim());
      setState("success");
    } catch {
      setState("error");
      setError(t("auth.resetRequestError"));
    }
  }

  return <section className="auth-card">
    <p className="eyebrow"><span /> {t("auth.customerAccess")}</p>
    <h1>{t("auth.forgotTitle")}</h1>
    <p>{t("auth.forgotCopy")}</p>
    {!available && <div className="error-banner" role="alert">{t("auth.unavailable")}</div>}
    {state === "success" ? <div className="inline-notice auth-reset-notice" role="status"><strong>{t("auth.resetEmailSentTitle")}</strong><span>{t("auth.resetEmailSent")}</span></div> : <form className="auth-form" onSubmit={(event) => void submit(event)} noValidate>
      <label><span>{t("auth.email")}</span><input required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} aria-invalid={Boolean(error)} /></label>
      {error && <div className="error-banner" role="alert">{error}</div>}
      <button className="button" type="submit" disabled={!available || state === "loading"}>{state === "loading" ? <><span className="spinner" /> {t("auth.sendingReset")}</> : t("auth.sendReset")}</button>
    </form>}
    <Link className="auth-switch" href="/login">{t("auth.backToLogin")}</Link>
  </section>;
}

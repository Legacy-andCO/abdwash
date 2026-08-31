"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "./auth-provider";
import { useI18n } from "./i18n-provider";
import type { TranslationKey } from "@/lib/i18n";

function safeReturnPath(value: string | null) {
  return value?.startsWith("/") && !value.startsWith("//") ? value : "/";
}

function customerAuthError(error: unknown, t: (key: TranslationKey) => string) {
  const message = error instanceof Error ? error.message.toLowerCase() : "";
  if (message.includes("invalid login credentials")) return t("auth.invalidCredentials");
  if (message.includes("not configured")) return t("auth.unavailable");
  return t("auth.checkDetails");
}

export function LoginForm() {
  const { t } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, signUp, available } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [fields, setFields] = useState({ firstName: "", surname: "", email: "", password: "", confirmPassword: "" });

  const update = (field: keyof typeof fields, value: string) => setFields((current) => ({ ...current, [field]: value }));
  const switchMode = () => {
    setMode((current) => current === "login" ? "signup" : "login");
    setError("");
    setNotice("");
  };

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (mode === "signup" && fields.password !== fields.confirmPassword) {
      setError(t("auth.passwordMismatch"));
      return;
    }
    setBusy(true);
    try {
      if (mode === "login") {
        await login(fields.email, fields.password);
        router.replace(safeReturnPath(searchParams.get("returnTo")));
      } else {
        const result = await signUp({ firstName: fields.firstName, surname: fields.surname, email: fields.email, password: fields.password });
        if (result.confirmationRequired) {
          setNotice(t("auth.checkEmail"));
        } else {
          router.replace(safeReturnPath(searchParams.get("returnTo")));
        }
      }
    } catch (reason) {
      setError(customerAuthError(reason, t));
    } finally {
      setBusy(false);
    }
  }

  return <section className="auth-card">
    <p className="eyebrow"><span /> {t("auth.customerAccess")}</p>
    <h1>{mode === "login" ? t("auth.loginTitle") : t("auth.signupTitle")}</h1>
    <p>{mode === "login" ? t("auth.loginCopy") : t("auth.signupCopy")}</p>
    {!available && <div className="error-banner" role="alert">{t("auth.unavailable")}</div>}
    {searchParams.get("passwordReset") === "success" && <div className="inline-notice" role="status"><strong>{t("auth.passwordUpdated")}</strong><span>{t("auth.passwordUpdatedLogin")}</span></div>}
    <form className="auth-form" onSubmit={(event) => void submit(event)}>
      {mode === "signup" && <div className="form-grid two"><label><span>{t("booking.details.firstName")}</span><input required autoComplete="given-name" value={fields.firstName} onChange={(event) => update("firstName", event.target.value)} /></label><label><span>{t("booking.details.surname")}</span><input required autoComplete="family-name" value={fields.surname} onChange={(event) => update("surname", event.target.value)} /></label></div>}
      <label><span>{t("auth.email")}</span><input required type="email" autoComplete="email" value={fields.email} onChange={(event) => update("email", event.target.value)} /></label>
      <div className="auth-field"><div className="auth-label-row"><label htmlFor="customer-password">{t("auth.password")}</label>{mode === "login" && <Link href="/forgot-password">{t("auth.forgotPassword")}</Link>}</div><input id="customer-password" required minLength={6} type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={fields.password} onChange={(event) => update("password", event.target.value)} /></div>
      {mode === "signup" && <label><span>{t("auth.confirmPassword")}</span><input required minLength={6} type="password" autoComplete="new-password" value={fields.confirmPassword} onChange={(event) => update("confirmPassword", event.target.value)} /></label>}
      {error && <div className="error-banner" role="alert">{error}</div>}
      {notice && <div className="inline-notice" role="status"><strong>{t("auth.oneMoreStep")}</strong><span>{notice}</span></div>}
      <button className="button" type="submit" disabled={busy || !available}>{busy ? <><span className="spinner" /> {t("booking.pleaseWait")}</> : mode === "login" ? t("auth.login") : t("auth.create")}</button>
    </form>
    <button className="auth-switch" type="button" onClick={switchMode}>{mode === "login" ? t("auth.switchSignup") : t("auth.switchLogin")}</button>
  </section>;
}

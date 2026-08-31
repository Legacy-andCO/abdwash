"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { TranslationKey } from "@/lib/i18n";
import { safeReturnPath } from "@/lib/site-url";
import { useAuth } from "./auth-provider";
import { useI18n } from "./i18n-provider";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function customerAuthError(
  error: unknown,
  t: (key: TranslationKey) => string,
) {
  const message = error instanceof Error ? error.message.toLowerCase() : "";
  if (message.includes("invalid login credentials"))
    return t("auth.invalidCredentials");
  if (message.includes("rate") || message.includes("seconds"))
    return t("auth.magicRateLimit");
  if (message.includes("not configured")) return t("auth.unavailable");
  return t("auth.checkDetails");
}

export function LoginForm() {
  const { t } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, requestMagicLink, available } = useAuth();
  const [mode, setMode] = useState<"magic" | "password">("magic");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [resendIn, setResendIn] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    if (resendIn <= 0) return;
    const timer = window.setInterval(
      () => setResendIn((seconds) => Math.max(0, seconds - 1)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [resendIn]);

  const returnTo = safeReturnPath(searchParams.get("returnTo"));

  async function sendMagicLink() {
    if (busy || resendIn > 0) return;
    setError("");
    const normalizedEmail = email.trim();
    if (!EMAIL_PATTERN.test(normalizedEmail)) {
      setError(t("auth.resetEmailInvalid"));
      return;
    }
    setBusy(true);
    try {
      await requestMagicLink(normalizedEmail, returnTo);
      setSent(true);
      setResendIn(60);
    } catch (reason) {
      setError(customerAuthError(reason, t));
    } finally {
      setBusy(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mode === "magic") {
      await sendMagicLink();
      return;
    }
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await login(email.trim(), password);
      router.replace(returnTo);
    } catch (reason) {
      setError(customerAuthError(reason, t));
    } finally {
      setBusy(false);
    }
  }

  function useAnotherEmail() {
    setSent(false);
    setResendIn(0);
    setEmail("");
    setError("");
  }

  function switchMode(nextMode: "magic" | "password") {
    setMode(nextMode);
    setSent(false);
    setResendIn(0);
    setError("");
  }

  return (
    <section className="auth-card">
      <p className="eyebrow">
        <span /> {t("auth.customerAccess")}
      </p>
      <h1>{t(mode === "magic" ? "auth.magicTitle" : "auth.loginTitle")}</h1>
      <p>{t(mode === "magic" ? "auth.magicCopy" : "auth.loginCopy")}</p>
      {!available && <div className="error-banner" role="alert">{t("auth.unavailable")}</div>}
      {searchParams.get("passwordReset") === "success" && (
        <div className="inline-notice" role="status">
          <strong>{t("auth.passwordUpdated")}</strong>
          <span>{t("auth.passwordUpdatedLogin")}</span>
        </div>
      )}
      {mode === "magic" && sent ? (
        <div className="auth-magic-sent" aria-live="polite">
          <div className="confirmation-burst" aria-hidden="true">✓</div>
          <h2>{t("auth.magicSentTitle")}</h2>
          <p>{t("auth.magicSentCopy")}</p>
          {error && <div className="error-banner" role="alert">{error}</div>}
          <button
            className="button"
            type="button"
            disabled={!available || busy || resendIn > 0}
            onClick={() => void sendMagicLink()}
          >
            {busy
              ? t("auth.magicSending")
              : resendIn > 0
                ? t("auth.magicResendCountdown", { seconds: resendIn })
                : t("auth.magicResend")}
          </button>
          <button className="auth-switch" type="button" onClick={useAnotherEmail}>
            {t("auth.magicAnotherEmail")}
          </button>
        </div>
      ) : (
        <form className="auth-form" onSubmit={(event) => void submit(event)} noValidate>
          <label>
            <span>{t("auth.email")}</span>
            <input
              required
              type="email"
              autoComplete="email"
              value={email}
              aria-invalid={Boolean(error) && mode === "magic"}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          {mode === "password" && (
            <div className="auth-field">
              <div className="auth-label-row">
                <label htmlFor="customer-password">{t("auth.password")}</label>
                <Link href="/forgot-password">{t("auth.forgotPassword")}</Link>
              </div>
              <input
                id="customer-password"
                required
                minLength={6}
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
          )}
          {error && <div className="error-banner" role="alert">{error}</div>}
          <button className="button" type="submit" disabled={busy || !available}>
            {busy
              ? t("booking.pleaseWait")
              : t(mode === "magic" ? "auth.magicSend" : "auth.login")}
          </button>
        </form>
      )}
      {!sent && (
        <div className="auth-alternative">
          <span>{t(mode === "magic" ? "auth.preferPassword" : "auth.preferMagic")}</span>
          <button
            className="auth-switch"
            type="button"
            onClick={() => switchMode(mode === "magic" ? "password" : "magic")}
          >
            {t(mode === "magic" ? "auth.usePassword" : "auth.useMagic")}
          </button>
        </div>
      )}
    </section>
  );
}

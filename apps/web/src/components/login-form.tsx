"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { TranslationKey } from "@/lib/i18n";
import { safeReturnPath } from "@/lib/site-url";
import { useAuth } from "./auth-provider";
import { useI18n } from "./i18n-provider";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function sanitizeOtpCode(value: string) {
  return value.replace(/\D/g, "").slice(0, 6);
}

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

function customerOtpError(
  error: unknown,
  t: (key: TranslationKey) => string,
) {
  const message = error instanceof Error ? error.message.toLowerCase() : "";
  if (message.includes("expired")) return t("auth.otpExpired");
  if (message.includes("invalid") || message.includes("token"))
    return t("auth.otpInvalid");
  return t("auth.otpUnexpected");
}

export function LoginForm() {
  const { t } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, requestMagicLink, verifyEmailOtp, signUp, available } = useAuth();
  const [mode, setMode] = useState<"magic" | "password" | "signup">("magic");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState<"magic" | "signup" | null>(null);
  const [resendIn, setResendIn] = useState(0);
  const [otpCode, setOtpCode] = useState("");
  const [error, setError] = useState("");
  const [passwordResetNotice, setPasswordResetNotice] = useState(
    searchParams.get("passwordReset") === "success",
  );

  useEffect(() => {
    if (searchParams.get("passwordReset") !== "success") return;
    const next = new URLSearchParams(searchParams.toString());
    next.delete("passwordReset");
    router.replace(`/login${next.size ? `?${next.toString()}` : ""}`);
  }, [router, searchParams]);

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
      setSent("magic");
      setPasswordResetNotice(false);
      setResendIn(60);
      setOtpCode("");
    } catch (reason) {
      setError(customerAuthError(reason, t));
    } finally {
      setBusy(false);
    }
  }

  async function verifyMagicCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || otpCode.length !== 6) return;
    setBusy(true);
    setError("");
    try {
      await verifyEmailOtp(email.trim(), otpCode);
      router.replace(returnTo);
    } catch (reason) {
      setError(customerOtpError(reason, t));
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
      if (mode === "signup") {
        if (!EMAIL_PATTERN.test(email.trim())) {
          setError(t("auth.resetEmailInvalid"));
          return;
        }
        if (password.length < 6) {
          setError(t("auth.passwordTooShort"));
          return;
        }
        if (password !== confirmPassword) {
          setError(t("auth.passwordMismatch"));
          return;
        }
        const result = await signUp({ email: email.trim(), password, returnTo });
        if (result.confirmationRequired) setSent("signup");
        else router.replace(returnTo);
      } else {
        await login(email.trim(), password);
        router.replace(returnTo);
      }
    } catch (reason) {
      setError(customerAuthError(reason, t));
    } finally {
      setBusy(false);
    }
  }

  function useAnotherEmail() {
    setSent(null);
    setResendIn(0);
    setEmail("");
    setOtpCode("");
    setError("");
  }

  function switchMode(nextMode: "magic" | "password" | "signup") {
    setMode(nextMode);
    setSent(null);
    setResendIn(0);
    setError("");
    setPassword("");
    setConfirmPassword("");
    setPasswordResetNotice(false);
  }

  return (
    <section className="auth-card">
      <p className="eyebrow">
        <span /> {t("auth.customerAccess")}
      </p>
      {!sent && <>
        <h1>{t(mode === "magic" ? "auth.magicTitle" : mode === "signup" ? "auth.signupTitle" : "auth.loginTitle")}</h1>
        <p>{t(mode === "magic" ? "auth.magicCopy" : mode === "signup" ? "auth.signupCopy" : "auth.loginCopy")}</p>
      </>}
      {!available && <div className="error-banner" role="alert">{t("auth.unavailable")}</div>}
      {passwordResetNotice && !sent && (
        <div className="inline-notice" role="status">
          <strong>{t("auth.passwordUpdated")}</strong>
          <span>{t("auth.passwordUpdatedLogin")}</span>
        </div>
      )}
      {sent ? (
        <div className="auth-magic-sent" aria-live="polite">
          <div className="confirmation-burst" aria-hidden="true">✓</div>
          <h2>{t(sent === "magic" ? "auth.magicSentTitle" : "auth.signupSentTitle")}</h2>
          {sent === "magic" ? (
            <div className="auth-delivery-copy">
              <p>{t("auth.magicSentCopy")}</p>
              <p className="auth-email-line">
                <span>{t("auth.magicSentTo")}</span>
                <strong dir="ltr">{email.trim()}</strong>
              </p>
              <p>{t("auth.magicSentDevice")}</p>
            </div>
          ) : <p>{t("auth.signupSentCopy")}</p>}
          {error && <div className="error-banner" role="alert">{error}</div>}
          {sent === "magic" && (
            <form className="auth-otp-form" onSubmit={(event) => void verifyMagicCode(event)}>
              <p className="auth-otp-heading">{t("auth.magicOtpHeading")}</p>
              <p>{t("auth.magicOtpPrompt")}</p>
              <label>
                <span>{t("auth.magicOtpCode")}</span>
                <input
                  aria-invalid={Boolean(error)}
                  autoComplete="one-time-code"
                  dir="ltr"
                  inputMode="numeric"
                  maxLength={6}
                  pattern="[0-9]{6}"
                  value={otpCode}
                  onChange={(event) => {
                    setOtpCode(sanitizeOtpCode(event.target.value));
                    setError("");
                  }}
                  onPaste={(event) => {
                    event.preventDefault();
                    setOtpCode(sanitizeOtpCode(event.clipboardData.getData("text")));
                    setError("");
                  }}
                />
              </label>
              <button className="button" type="submit" disabled={!available || busy || otpCode.length !== 6}>
                {busy ? t("auth.magicOtpVerifying") : t("auth.magicOtpVerify")}
              </button>
            </form>
          )}
          {sent === "magic" && <button
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
            </button>}
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
          {(mode === "password" || mode === "signup") && (
            <div className="auth-field">
              <div className="auth-label-row">
                <label htmlFor="customer-password">{t("auth.password")}</label>
                {mode === "password" && <Link href="/forgot-password">{t("auth.forgotPassword")}</Link>}
              </div>
              <input
                id="customer-password"
                required
                minLength={6}
                type="password"
                autoComplete={mode === "signup" ? "new-password" : "current-password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
          )}
          {mode === "signup" && <label>
            <span>{t("auth.confirmPassword")}</span>
            <input required minLength={6} type="password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
          </label>}
          {error && <div className="error-banner" role="alert">{error}</div>}
          <button className="button" type="submit" disabled={busy || !available}>
            {busy
              ? t("booking.pleaseWait")
              : t(mode === "magic" ? "auth.magicSend" : mode === "signup" ? "auth.signup" : "auth.login")}
          </button>
        </form>
      )}
      {!sent && mode === "magic" && (
        <div className="auth-alternative">
          <span>{t("auth.preferPassword")}</span>
          <button
            className="auth-switch"
            type="button"
            onClick={() => switchMode("password")}
          >
            {t("auth.usePassword")}
          </button>
        </div>
      )}
      {!sent && mode === "password" && <div className="auth-alternative auth-alternative-stack">
        <span>{t("auth.noAccount")}</span>
        <button className="auth-switch" type="button" onClick={() => switchMode("signup")}>{t("auth.signupWithPassword")}</button>
        <button className="auth-switch" type="button" onClick={() => switchMode("magic")}>{t("auth.useMagic")}</button>
      </div>}
      {!sent && mode === "signup" && <div className="auth-alternative auth-alternative-stack">
        <span>{t("auth.alreadyAccount")}</span>
        <button className="auth-switch" type="button" onClick={() => switchMode("password")}>{t("auth.loginWithPassword")}</button>
        <button className="auth-switch" type="button" onClick={() => switchMode("magic")}>{t("auth.backPasswordless")}</button>
      </div>}
    </section>
  );
}

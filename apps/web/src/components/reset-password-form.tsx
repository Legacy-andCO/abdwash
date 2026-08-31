"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { useAuth } from "./auth-provider";
import { useI18n } from "./i18n-provider";

export function ResetPasswordForm() {
  const { t } = useI18n();
  const router = useRouter();
  const { available, loading, recoveryMode, updateRecoveredPassword, user } = useAuth();
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError("");
    if (password.length < 6) {
      setError(t("auth.passwordMinimum"));
      return;
    }
    if (password !== confirmation) {
      setError(t("auth.passwordMismatch"));
      return;
    }
    setBusy(true);
    try {
      await updateRecoveredPassword(password);
      router.replace("/login?passwordReset=success");
    } catch {
      setError(t("auth.updatePasswordError"));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <section className="auth-card auth-confirmation" aria-live="polite"><span className="spinner dark" /><h1>{t("auth.checkingReset")}</h1><p>{t("auth.confirmingCopy")}</p></section>;

  if (!available || !recoveryMode || !user) return <section className="auth-card auth-confirmation" aria-live="polite"><h1>{t("auth.resetInvalidTitle")}</h1><p>{t("auth.resetInvalidCopy")}</p><Link className="button" href="/forgot-password">{t("auth.requestNewReset")}</Link></section>;

  return <section className="auth-card">
    <p className="eyebrow"><span /> {t("auth.customerAccess")}</p>
    <h1>{t("auth.newPasswordTitle")}</h1>
    <p>{t("auth.newPasswordCopy")}</p>
    <form className="auth-form" onSubmit={(event) => void submit(event)}>
      <label><span>{t("auth.newPassword")}</span><input required minLength={6} type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
      <label><span>{t("auth.confirmNewPassword")}</span><input required minLength={6} type="password" autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label>
      {error && <div className="error-banner" role="alert">{error}</div>}
      <button className="button" type="submit" disabled={busy}>{busy ? <><span className="spinner" /> {t("auth.updatingPassword")}</> : t("auth.updatePassword")}</button>
    </form>
  </section>;
}

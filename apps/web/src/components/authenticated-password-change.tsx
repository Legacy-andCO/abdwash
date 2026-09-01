"use client";

import { type FormEvent, useState } from "react";
import {
  AuthenticatedPasswordUpdateError,
  useAuth,
} from "./auth-provider";
import { useI18n } from "./i18n-provider";

export function AuthenticatedPasswordChange() {
  const { t } = useI18n();
  const {
    user,
    updateAuthenticatedPassword,
    requestPasswordReauthentication,
  } = useAuth();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [nonce, setNonce] = useState("");
  const [needsReauthentication, setNeedsReauthentication] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  if (!user) return null;

  function resetForm() {
    setOpen(false);
    setPassword("");
    setConfirmation("");
    setNonce("");
    setNeedsReauthentication(false);
    setError("");
  }

  function close() {
    if (busy) return;
    resetForm();
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError("");
    setSuccess("");
    if (!password || !confirmation) {
      setError(t("profile.passwordRequired"));
      return;
    }
    if (password !== confirmation) {
      setError(t("auth.passwordMismatch"));
      return;
    }
    if (needsReauthentication && !nonce.trim()) {
      setError(t("profile.passwordCodeRequired"));
      return;
    }

    setBusy(true);
    try {
      await updateAuthenticatedPassword(
        password,
        needsReauthentication ? nonce.trim() : undefined,
      );
      resetForm();
      setSuccess(t("profile.passwordUpdated"));
    } catch (reason) {
      if (
        reason instanceof AuthenticatedPasswordUpdateError &&
        reason.code === "reauthentication_needed"
      ) {
        try {
          await requestPasswordReauthentication();
          setNeedsReauthentication(true);
          setError("");
        } catch {
          setError(t("profile.passwordUpdateError"));
        }
      } else if (
        reason instanceof AuthenticatedPasswordUpdateError &&
        reason.code === "weak_password"
      ) {
        setError(t("profile.passwordPolicyError"));
      } else if (
        reason instanceof AuthenticatedPasswordUpdateError &&
        (reason.code === "reauth_nonce_missing" ||
          reason.code === "reauthentication_not_valid")
      ) {
        setError(t("profile.passwordCodeInvalid"));
      } else {
        setError(t("profile.passwordUpdateError"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="profile-panel security-panel">
      <div className="security-panel-heading">
        <div>
          <p className="eyebrow">
            <span /> {t("profile.security")}
          </p>
          <h2>{t("auth.password")}</h2>
        </div>
        {!open && (
          <button
            className="button button-ghost"
            type="button"
            onClick={() => {
              setOpen(true);
              setError("");
              setSuccess("");
            }}
          >
            {t("profile.changePassword")}
          </button>
        )}
      </div>
      {success && (
        <div className="inline-notice" role="status">
          <strong>{success}</strong>
        </div>
      )}
      {open && (
        <form className="security-password-form" onSubmit={(event) => void submit(event)}>
          <h3>{t("profile.changePassword")}</h3>
          <div className="form-grid two">
            <label>
              <span>{t("auth.newPassword")}</span>
              <input
                type="password"
                autoComplete="new-password"
                aria-required="true"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <label>
              <span>{t("auth.confirmNewPassword")}</span>
              <input
                type="password"
                autoComplete="new-password"
                aria-required="true"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
              />
            </label>
          </div>
          {needsReauthentication && (
            <label className="security-code-field">
              <span>{t("profile.passwordCode")}</span>
              <input
                className="bidi-ltr"
                inputMode="numeric"
                autoComplete="one-time-code"
                aria-required="true"
                value={nonce}
                onChange={(event) => setNonce(event.target.value)}
              />
              <small>{t("profile.passwordCodeSent")}</small>
            </label>
          )}
          {error && (
            <div className="error-banner" role="alert">
              {error}
            </div>
          )}
          <div className="profile-actions">
            <button className="button" type="submit" disabled={busy}>
              {busy ? t("auth.updatingPassword") : t("auth.updatePassword")}
            </button>
            <button
              className="button button-ghost"
              type="button"
              disabled={busy}
              onClick={close}
            >
              {t("common.cancel")}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

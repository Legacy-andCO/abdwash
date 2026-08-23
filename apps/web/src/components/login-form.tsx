"use client";

import { FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "./auth-provider";

function safeReturnPath(value: string | null) {
  return value?.startsWith("/") && !value.startsWith("//") ? value : "/";
}

function customerAuthError(error: unknown) {
  const message = error instanceof Error ? error.message.toLowerCase() : "";
  if (message.includes("invalid login credentials")) return "The email or password is incorrect.";
  if (message.includes("not configured")) return "Customer login is temporarily unavailable.";
  return "We couldn't complete that request. Please check your details and try again.";
}

export function LoginForm() {
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
      setError("Passwords do not match.");
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
          setNotice("Check your email to confirm your account, then return here to log in.");
        } else {
          router.replace(safeReturnPath(searchParams.get("returnTo")));
        }
      }
    } catch (reason) {
      setError(customerAuthError(reason));
    } finally {
      setBusy(false);
    }
  }

  return <section className="auth-card">
    <p className="eyebrow"><span /> Customer access</p>
    <h1>{mode === "login" ? "Welcome back." : "Create your account."}</h1>
    <p>{mode === "login" ? "Log in to continue with AbdWash." : "A simple account now; booking history and saved details will come later."}</p>
    {!available && <div className="error-banner" role="alert">Customer login is temporarily unavailable.</div>}
    <form className="auth-form" onSubmit={(event) => void submit(event)}>
      {mode === "signup" && <div className="form-grid two"><label><span>First name</span><input required autoComplete="given-name" value={fields.firstName} onChange={(event) => update("firstName", event.target.value)} /></label><label><span>Surname</span><input required autoComplete="family-name" value={fields.surname} onChange={(event) => update("surname", event.target.value)} /></label></div>}
      <label><span>Email address</span><input required type="email" autoComplete="email" value={fields.email} onChange={(event) => update("email", event.target.value)} /></label>
      <label><span>Password</span><input required minLength={6} type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={fields.password} onChange={(event) => update("password", event.target.value)} /></label>
      {mode === "signup" && <label><span>Confirm password</span><input required minLength={6} type="password" autoComplete="new-password" value={fields.confirmPassword} onChange={(event) => update("confirmPassword", event.target.value)} /></label>}
      {error && <div className="error-banner" role="alert">{error}</div>}
      {notice && <div className="inline-notice" role="status"><strong>One more step.</strong><span>{notice}</span></div>}
      <button className="button" type="submit" disabled={busy || !available}>{busy ? <><span className="spinner" /> Please wait</> : mode === "login" ? "Log in" : "Create account"}</button>
    </form>
    <button className="auth-switch" type="button" onClick={switchMode}>{mode === "login" ? "New to AbdWash? Create account" : "Already have an account? Log in"}</button>
  </section>;
}

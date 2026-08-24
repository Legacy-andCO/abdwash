"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getSupabaseBrowserClient } from "@/lib/supabase-client";

type ConfirmationState = "loading" | "success" | "failed";

export function AuthConfirmation() {
  const [state, setState] = useState<ConfirmationState>("loading");

  useEffect(() => {
    let active = true;
    async function confirm() {
      const client = getSupabaseBrowserClient();
      if (!client) {
        if (active) setState("failed");
        return;
      }
      const url = new URL(window.location.href);
      const fragment = new URLSearchParams(url.hash.replace(/^#/, ""));
      if (url.searchParams.has("error") || fragment.has("error")) {
        if (active) setState("failed");
        return;
      }
      try {
        const code = url.searchParams.get("code");
        if (code) {
          const { error } = await client.auth.exchangeCodeForSession(code);
          if (error) throw error;
        } else {
          const { data, error } = await client.auth.getSession();
          if (error || !data.session) throw error ?? new Error("No confirmed session");
        }
        if (active) setState("success");
      } catch {
        if (active) setState("failed");
      }
    }
    void confirm();
    return () => { active = false; };
  }, []);

  return <section className="auth-card auth-confirmation" aria-live="polite">
    {state === "loading" && <><span className="spinner dark" /><h1>Confirming your account…</h1><p>Please keep this page open for a moment.</p></>}
    {state === "success" && <><div className="confirmation-burst" aria-hidden="true">✓</div><h1>Email confirmed.</h1><p>Your AbdWash account is ready.</p><Link className="button" href="/account">View your bookings</Link></>}
    {state === "failed" && <><h1>We couldn’t confirm that link.</h1><p>It may have expired or already been used. Return to login and request a new confirmation by signing up again.</p><Link className="button" href="/login">Return to login</Link></>}
  </section>;
}

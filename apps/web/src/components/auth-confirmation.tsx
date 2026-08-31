"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { safeReturnPath } from "@/lib/site-url";
import { getSupabaseBrowserClient } from "@/lib/supabase-client";
import { useI18n } from "./i18n-provider";

type ConfirmationState = "loading" | "success" | "failed";

export function AuthConfirmation() {
  const { t } = useI18n();
  const router = useRouter();
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
        if (active) {
          setState("success");
          router.replace(safeReturnPath(url.searchParams.get("returnTo")));
        }
      } catch {
        if (active) setState("failed");
      }
    }
    void confirm();
    return () => { active = false; };
  }, [router]);

  return <section className="auth-card auth-confirmation" aria-live="polite">
    {state === "loading" && <><span className="spinner dark" /><h1>{t("auth.confirming")}</h1><p>{t("auth.confirmingCopy")}</p></>}
    {state === "success" && <><div className="confirmation-burst" aria-hidden="true">✓</div><h1>{t("auth.confirmed")}</h1><p>{t("auth.confirmedCopy")}</p><Link className="button" href="/account">{t("auth.viewBookings")}</Link></>}
    {state === "failed" && <><h1>{t("auth.confirmFailed")}</h1><p>{t("auth.confirmFailedCopy")}</p><Link className="button" href="/login">{t("auth.returnLogin")}</Link></>}
  </section>;
}

"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Session, SupabaseClient, User } from "@supabase/supabase-js";
import { usePathname, useRouter } from "next/navigation";
import { getSupabaseBrowserClient } from "@/lib/supabase-client";
import { getAuthConfirmUrl, getPublicSiteUrl } from "@/lib/site-url";

type SignUpInput = { firstName: string; surname: string; email: string; password: string };
type AuthContextValue = {
  user: User | null;
  loading: boolean;
  available: boolean;
  recoveryMode: boolean;
  requestMagicLink: (email: string, returnTo?: string | null) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  signUp: (input: SignUpInput) => Promise<{ confirmationRequired: boolean }>;
  requestPasswordReset: (email: string) => Promise<void>;
  updateRecoveredPassword: (password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);
const RECOVERY_SESSION_KEY = "trifecta-password-recovery";

function hasRecoveryIntent(): boolean {
  if (typeof window === "undefined") return false;
  const url = new URL(window.location.href);
  const fragment = new URLSearchParams(url.hash.replace(/^#/, ""));
  return (
    url.searchParams.get("type") === "recovery" ||
    fragment.get("type") === "recovery" ||
    window.sessionStorage.getItem(RECOVERY_SESSION_KEY) === "1"
  );
}

export function AuthProvider({ children, client: clientOverride }: { children: ReactNode; client?: SupabaseClient | null }) {
  const pathname = usePathname();
  const router = useRouter();
  const client = clientOverride === undefined ? getSupabaseBrowserClient() : clientOverride;
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(client !== null);
  const [recoveryMode, setRecoveryMode] = useState(hasRecoveryIntent);

  useEffect(() => {
    let active = true;
    if (!client) return;
    void client.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      setLoading(false);
    });
    const { data: { subscription } } = client.auth.onAuthStateChange((event, nextSession) => {
      if (!active) return;
      setSession(nextSession);
      if (event === "PASSWORD_RECOVERY") {
        window.sessionStorage.setItem(RECOVERY_SESSION_KEY, "1");
        setRecoveryMode(true);
      } else if (event === "SIGNED_OUT") {
        window.sessionStorage.removeItem(RECOVERY_SESSION_KEY);
        setRecoveryMode(false);
      }
      setLoading(false);
    });
    return () => { active = false; subscription.unsubscribe(); };
  }, [client]);

  useEffect(() => {
    if (recoveryMode && pathname !== "/auth/reset-password") {
      router.replace("/auth/reset-password");
    }
  }, [pathname, recoveryMode, router]);

  const value = useMemo<AuthContextValue>(() => ({
    user: session?.user ?? null,
    loading,
    available: client !== null,
    recoveryMode,
    requestMagicLink: async (email, returnTo) => {
      if (!client) throw new Error("Customer login is not configured.");
      const { error } = await client.auth.signInWithOtp({
        email,
        options: { emailRedirectTo: getAuthConfirmUrl(returnTo ?? null) },
      });
      if (error) throw new Error(error.message);
    },
    login: async (email, password) => {
      if (!client) throw new Error("Customer login is not configured.");
      const { data, error } = await client.auth.signInWithPassword({ email, password });
      if (error) throw new Error(error.message);
      setSession(data.session);
    },
    signUp: async ({ firstName, surname, email, password }) => {
      if (!client) throw new Error("Customer sign-up is not configured.");
      const { data, error } = await client.auth.signUp({
        email,
        password,
        options: {
          data: { first_name: firstName, surname },
          emailRedirectTo: `${getPublicSiteUrl()}/auth/confirm`,
        },
      });
      if (error) throw new Error(error.message);
      setSession(data.session);
      return { confirmationRequired: data.session === null };
    },
    requestPasswordReset: async (email) => {
      if (!client) throw new Error("Customer login is not configured.");
      const { error } = await client.auth.resetPasswordForEmail(email, {
        redirectTo: `${getPublicSiteUrl()}/auth/reset-password`,
      });
      if (error) throw new Error(error.message);
    },
    updateRecoveredPassword: async (password) => {
      if (!client || !session || !recoveryMode) {
        throw new Error("Password recovery session is unavailable.");
      }
      const { error } = await client.auth.updateUser({ password });
      if (error) throw new Error(error.message);
      await client.auth.signOut({ scope: "local" });
      window.sessionStorage.removeItem(RECOVERY_SESSION_KEY);
      setRecoveryMode(false);
      setSession(null);
    },
    logout: async () => {
      if (!client) return;
      const { error } = await client.auth.signOut({ scope: "local" });
      if (error) throw new Error(error.message);
      setSession(null);
    },
  }), [client, loading, recoveryMode, session]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider.");
  return value;
}

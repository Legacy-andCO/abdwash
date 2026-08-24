"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Session, SupabaseClient, User } from "@supabase/supabase-js";
import { getSupabaseBrowserClient } from "@/lib/supabase-client";
import { getPublicSiteUrl } from "@/lib/site-url";

type SignUpInput = { firstName: string; surname: string; email: string; password: string };
type AuthContextValue = {
  user: User | null;
  loading: boolean;
  available: boolean;
  login: (email: string, password: string) => Promise<void>;
  signUp: (input: SignUpInput) => Promise<{ confirmationRequired: boolean }>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children, client: clientOverride }: { children: ReactNode; client?: SupabaseClient | null }) {
  const client = clientOverride === undefined ? getSupabaseBrowserClient() : clientOverride;
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(client !== null);

  useEffect(() => {
    let active = true;
    if (!client) return;
    void client.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      setLoading(false);
    });
    const { data: { subscription } } = client.auth.onAuthStateChange((_event, nextSession) => {
      if (!active) return;
      setSession(nextSession);
      setLoading(false);
    });
    return () => { active = false; subscription.unsubscribe(); };
  }, [client]);

  const value = useMemo<AuthContextValue>(() => ({
    user: session?.user ?? null,
    loading,
    available: client !== null,
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
    logout: async () => {
      if (!client) return;
      const { error } = await client.auth.signOut({ scope: "local" });
      if (error) throw new Error(error.message);
      setSession(null);
    },
  }), [client, loading, session]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider.");
  return value;
}

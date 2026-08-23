import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let browserClient: SupabaseClient | null | undefined;

export function getSupabaseBrowserClient(): SupabaseClient | null {
  if (browserClient !== undefined) return browserClient;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonymousKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonymousKey) {
    browserClient = null;
    return browserClient;
  }
  browserClient = createClient(url, anonymousKey, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
  });
  return browserClient;
}

export async function getSupabaseAccessToken(): Promise<string | null> {
  const client = getSupabaseBrowserClient();
  if (!client) return null;
  const { data, error } = await client.auth.getSession();
  if (error) return null;
  return data.session?.access_token ?? null;
}

export function resetSupabaseBrowserClientForTests() {
  browserClient = undefined;
}

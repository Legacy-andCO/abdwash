import type { Session } from "@supabase/supabase-js";
import { useEffect, useState } from "react";
import { ActivityIndicator, SafeAreaView, StyleSheet, Text } from "react-native";
import { AppButton } from "./components/ui";
import { getContext, supabase, type StaffContext } from "./lib";
import { OperationsShell } from "./navigation/OperationsShell";
import { LoginScreen } from "./screens/LoginScreen";
import { colors, spacing } from "./theme";

export default function App() {
  const [session, setSession] = useState<Session | null | undefined>();
  const [context, setContext] = useState<StaffContext | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { void supabase.auth.getSession().then(({ data }) => setSession(data.session)); const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, value) => setSession(value)); return () => subscription.unsubscribe(); }, []);
  useEffect(() => { if (session === undefined) return; if (!session) { setContext(null); setError(""); return; } setError(""); void getContext(session).then(setContext).catch((reason) => setError(reason instanceof Error && reason.message === "STAFF_ACCESS_REQUIRED" ? "This account does not have staff access." : "Unable to verify staff access.")); }, [session]);
  if (session === undefined || (session && !context && !error)) return <SafeAreaView style={styles.center}><ActivityIndicator color={colors.primary} /><Text style={styles.text}>Restoring secure session…</Text></SafeAreaView>;
  if (!session) return <LoginScreen />;
  if (!context) return <SafeAreaView style={styles.center}><Text style={styles.title}>{error}</Text><AppButton title="Back to login" onPress={() => void supabase.auth.signOut()} /></SafeAreaView>;
  return <OperationsShell context={context} />;
}

const styles = StyleSheet.create({ center: { flex: 1, justifyContent: "center", padding: spacing.xl, gap: spacing.md, backgroundColor: colors.background }, title: { color: colors.text, fontSize: 24, fontWeight: "900", textAlign: "center" }, text: { color: colors.textSecondary, textAlign: "center" } });

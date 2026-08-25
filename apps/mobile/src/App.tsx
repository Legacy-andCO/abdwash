import type { Session } from "@supabase/supabase-js";
import { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text } from "react-native";
import {
  initialWindowMetrics,
  SafeAreaProvider,
  SafeAreaView,
} from "react-native-safe-area-context";
import { AppButton } from "./components/ui";
import {
  OperationsCacheProvider,
  prepareOperationalLogout,
} from "./cache/queryClient";
import { getContext, supabase, type StaffContext } from "./lib";
import { OperationsShell } from "./navigation/OperationsShell";
import { LoginScreen } from "./screens/LoginScreen";
import { colors, spacing } from "./theme";

function AuthenticatedApp() {
  const [session, setSession] = useState<Session | null | undefined>();
  const [context, setContext] = useState<StaffContext | null>(null);
  const [contextUserId, setContextUserId] = useState<string | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    void supabase.auth
      .getSession()
      .then(({ data }) => setSession(data.session));
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, value) => {
      if (event === "SIGNED_OUT") void prepareOperationalLogout();
      setSession(value);
    });
    return () => subscription.unsubscribe();
  }, []);
  useEffect(() => {
    if (session === undefined) return;
    if (!session) {
      setContext(null);
      setContextUserId(null);
      setError("");
      return;
    }
    setError("");
    let active = true;
    void getContext(session)
      .then((value) => {
        if (active) {
          setContext(value);
          setContextUserId(session.user.id);
        }
      })
      .catch((reason) => {
        if (active)
          setError(
            reason instanceof Error &&
              reason.message === "STAFF_ACCESS_REQUIRED"
              ? "This account does not have staff access."
              : "Unable to verify staff access.",
          );
      });
    return () => {
      active = false;
    };
  }, [session?.user.id]);
  const verifiedContext =
    session && contextUserId === session.user.id ? context : null;
  if (session === undefined || (session && !verifiedContext && !error))
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator color={colors.primary} />
        <Text style={styles.text}>Restoring secure session…</Text>
      </SafeAreaView>
    );
  if (!session) return <LoginScreen />;
  if (!verifiedContext)
    return (
      <SafeAreaView style={styles.center}>
        <Text style={styles.title}>{error}</Text>
        <AppButton
          title="Back to login"
          onPress={() => void supabase.auth.signOut()}
        />
      </SafeAreaView>
    );
  return <OperationsShell context={verifiedContext} />;
}

export default function App() {
  return (
    <SafeAreaProvider initialMetrics={initialWindowMetrics}>
      <OperationsCacheProvider>
        <AuthenticatedApp />
      </OperationsCacheProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    justifyContent: "center",
    padding: spacing.xl,
    gap: spacing.md,
    backgroundColor: colors.background,
  },
  title: {
    color: colors.text,
    fontSize: 24,
    fontWeight: "900",
    textAlign: "center",
  },
  text: { color: colors.textSecondary, textAlign: "center" },
});

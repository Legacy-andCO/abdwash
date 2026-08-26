import type { Session } from "@supabase/supabase-js";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
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
import { validatePasswordConfirmation } from "./forms/password";
import { getContext, supabase, updateProfile, type StaffContext } from "./lib";
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
  if (verifiedContext.must_change_password) {
    return (
      <RequiredPasswordChange
        onChanged={() =>
          setContext((current) =>
            current ? { ...current, must_change_password: false } : current,
          )
        }
      />
    );
  }
  return <OperationsShell context={verifiedContext} />;
}

function RequiredPasswordChange({ onChanged }: { onChanged: () => void }) {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit() {
    const validation = validatePasswordConfirmation(password, confirmation);
    if (validation) {
      Alert.alert("Password not changed", validation);
      return;
    }
    setBusy(true);
    try {
      await updateProfile({ password });
      setPassword("");
      setConfirmation("");
      onChanged();
      Alert.alert("Password changed successfully.");
    } catch {
      Alert.alert(
        "Password not changed",
        "Choose a valid password and try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <SafeAreaView style={styles.requiredPasswordScreen}>
      <View style={styles.requiredPasswordCard}>
        <Text style={styles.title}>Change your password</Text>
        <Text style={styles.text}>
          Your temporary password must be replaced before you continue.
        </Text>
        <TextInput
          accessibilityLabel="New password"
          autoCapitalize="none"
          secureTextEntry
          style={styles.field}
          placeholder="New password"
          value={password}
          onChangeText={setPassword}
        />
        <TextInput
          accessibilityLabel="Confirm new password"
          autoCapitalize="none"
          secureTextEntry
          style={styles.field}
          placeholder="Confirm new password"
          value={confirmation}
          onChangeText={setConfirmation}
        />
        <AppButton
          title={busy ? "Updating…" : "Update password"}
          disabled={busy}
          loading={busy}
          onPress={() => void submit()}
        />
        <AppButton
          title="Sign out"
          tone="secondary"
          disabled={busy}
          onPress={() =>
            void (async () => {
              await prepareOperationalLogout();
              await supabase.auth.signOut();
            })()
          }
        />
      </View>
    </SafeAreaView>
  );
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
  requiredPasswordScreen: {
    flex: 1,
    justifyContent: "center",
    padding: spacing.xl,
    backgroundColor: colors.background,
  },
  requiredPasswordCard: {
    gap: spacing.md,
    padding: spacing.xl,
    borderRadius: 18,
    backgroundColor: colors.surface,
  },
  field: {
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    color: colors.text,
  },
});

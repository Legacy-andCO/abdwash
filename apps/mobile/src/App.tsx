import { t } from "./i18n";
import { Alert } from "./alert";
import { signOutFromStaffApp } from "./authSignOut";
import type { Session } from "@supabase/supabase-js";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  AppState,
  Platform,
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
import { PrivilegedMfa } from "./components/PrivilegedMfa";
import { subscribeMfaRequired, subscribeSessionRejected } from "./mfa-events";
import { StaffLanguage, useStaffLanguage } from "./components/StaffLanguage";

function AuthenticatedApp() {
  const [session, setSession] = useState<Session | null | undefined>();
  const [context, setContext] = useState<StaffContext | null>(null);
  const [contextUserId, setContextUserId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [mfaRequired, setMfaRequired] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => subscribeSessionRejected(() => {
    setContext(null);
    setRevision(v => v + 1);
  }), []);
  useEffect(() => subscribeMfaRequired(() => { setMfaRequired(true); setContext(null); }), []);
  useEffect(() => {
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, value) => {
      if (event === "SIGNED_OUT") { setMfaRequired(false); void prepareOperationalLogout(); }
      setSession(value);
    });
    if (Platform.OS === "web") return () => subscription.unsubscribe();
    const updateRefresh = (state: string | null) => {
      if (state === "active") {
        void supabase.auth.startAutoRefresh();
        setRevision(v => v + 1);
      } else {
        void supabase.auth.stopAutoRefresh();
      }
    };
    updateRefresh(AppState.currentState);
    const lifecycle = AppState.addEventListener("change", updateRefresh);
    return () => {
      lifecycle.remove();
      subscription.unsubscribe();
      void supabase.auth.stopAutoRefresh();
    };
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
    void getContext()
      .then((value) => {
        if (active) {
          setContext(value);
          setContextUserId(session.user.id);
        }
      })
      .catch((reason) => {
        if (active && ["MFA_REQUIRED", "MFA_REAUTHENTICATION_REQUIRED"].includes(reason?.code ?? reason?.message)) {
          setMfaRequired(true); setContext(null); return;
        }
        if (active && [401, 403].includes(reason?.status)) setContext(null);
        if (active)
          setError(
            reason instanceof Error &&
              reason.message === "STAFF_ACCESS_REQUIRED"
              ? t("This account does not have staff access.")
              : t("Unable to verify staff access."),
          );
      });
    return () => {
      active = false;
    };
  }, [session?.user.id, session?.access_token, revision]);
  const verifiedContext =
    session && contextUserId === session.user.id ? context : null;
  if (session && mfaRequired) return <PrivilegedMfa key={session.user.id} userId={session.user.id} onVerified={() => { setMfaRequired(false); setRevision(v => v + 1); }} />;
  if (session === undefined || (session && !verifiedContext && !error))
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator color={colors.primary} />
        <Text style={styles.text}>{t("Restoring secure session…")}</Text>
      </SafeAreaView>
    );
  if (!session) return <LoginScreen />;
  if (!verifiedContext)
    return (
      <SafeAreaView style={styles.center}>
        <Text style={styles.title}>{t(error)}</Text>
        <AppButton title={t("Try again")} onPress={() => setRevision(v => v + 1)} />
        <AppButton
          title={t("Back to login")}
          onPress={() => void signOutFromStaffApp()}
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
      Alert.alert(t("Password not changed"), validation);
      return;
    }
    setBusy(true);
    try {
      await updateProfile({ password });
      setPassword("");
      setConfirmation("");
      onChanged();
      Alert.alert(t("Password changed successfully."));
    } catch {
      Alert.alert(
        t("Password not changed"),
        t("Choose a valid password and try again."),
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <SafeAreaView style={styles.requiredPasswordScreen}>
      <View style={styles.requiredPasswordCard}>
        <Text style={styles.title}>{t("Change your password")}</Text>
        <Text style={styles.text}>
          {" " + t("Your temporary password must be replaced before you continue.") + " "}</Text>
        <TextInput
          accessibilityLabel={t("New password")}
          autoCapitalize="none"
          secureTextEntry
          style={styles.field}
          placeholder={t("New password")}
          value={password}
          onChangeText={setPassword}
        />
        <TextInput
          accessibilityLabel={t("Confirm new password")}
          autoCapitalize="none"
          secureTextEntry
          style={styles.field}
          placeholder={t("Confirm new password")}
          value={confirmation}
          onChangeText={setConfirmation}
        />
        <AppButton
          title={busy ? t("Updating…") : t("Update password")}
          disabled={busy}
          loading={busy}
          onPress={() => void submit()}
        />
        <AppButton
          title={t("Sign out")}
          tone="secondary"
          disabled={busy}
          onPress={() => void signOutFromStaffApp()}
        />
      </View>
    </SafeAreaView>
  );
}

export default function App() {
  const language = useStaffLanguage();
  return (
    <SafeAreaProvider initialMetrics={initialWindowMetrics}>
      <OperationsCacheProvider>
        <View style={{ flex: 1, direction: language === "ar" ? "rtl" : "ltr" }}>
          <StaffLanguage />
          <AuthenticatedApp />
        </View>
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

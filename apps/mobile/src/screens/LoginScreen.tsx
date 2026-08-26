import { useState } from "react";
import {
  KeyboardAvoidingView,
  Image,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { AppButton, uiStyles } from "../components/ui";
import { supabase } from "../lib";
import { staffLoginEmail } from "../staff-login";
import { colors, spacing } from "../theme";

export function LoginScreen() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function login() {
    setBusy(true);
    setError("");
    try {
      const result = await supabase.auth.signInWithPassword({
        email: staffLoginEmail(username),
        password,
      });
      if (result.error) setError("Username or password is incorrect.");
    } catch {
      setError("Enter a valid username.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <SafeAreaView
      edges={["top", "bottom", "left", "right"]}
      style={styles.screen}
    >
      <KeyboardAvoidingView
        style={styles.fill}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={styles.center}
        >
          <View style={styles.brand}>
            <Text style={styles.eyebrow}>STAFF OPERATIONS</Text>
            <Image source={require("../../assets/trifecta-logo.png")} resizeMode="contain" style={styles.logo} accessibilityLabel="Trifecta" />
            <Text style={styles.subtitle}>
              Your day, team and jobs in one place.
            </Text>
          </View>
          <View style={styles.form}>
            <Text style={uiStyles.label}>USERNAME</Text>
            <TextInput
              style={uiStyles.field}
              accessibilityLabel="Username"
              autoCapitalize="none"
              autoCorrect={false}
              value={username}
              onChangeText={setUsername}
              placeholder="Username"
            />
            <Text style={uiStyles.label}>PASSWORD</Text>
            <TextInput
              style={uiStyles.field}
              accessibilityLabel="Password"
              secureTextEntry
              value={password}
              onChangeText={setPassword}
              placeholder="Password"
              onSubmitEditing={() => void login()}
            />
            {error ? (
              <Text accessibilityRole="alert" style={uiStyles.error}>
                {error}
              </Text>
            ) : null}
            <AppButton
              title="Log in"
              disabled={busy}
              loading={busy}
              onPress={() => void login()}
            />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  fill: { flex: 1 },
  center: {
    flexGrow: 1,
    justifyContent: "center",
    padding: spacing.xl,
    gap: spacing.xxl,
  },
  brand: { gap: spacing.sm },
  eyebrow: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 1.8,
  },
  logo: { height: 74, width: 298, maxWidth: "100%" },
  subtitle: { color: colors.textSecondary, fontSize: 16 },
  form: { gap: spacing.md },
});

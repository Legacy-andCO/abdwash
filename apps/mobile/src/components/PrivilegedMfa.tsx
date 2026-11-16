import { useEffect, useRef, useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { SvgXml } from "react-native-svg";
import { supabase } from "../lib";
import { colors, radii, spacing } from "../theme";
import { AppButton, uiStyles } from "./ui";

type Authenticator = { id: string; qr?: string; incomplete?: boolean };
// Share only in-flight initialization, including React remounts. Never persist secrets.
const initializing = new Map<string, Promise<Authenticator>>();
async function prepareAuthenticator(restart: boolean): Promise<Authenticator> {
  const listed = await supabase.auth.mfa.listFactors();
  if (listed.error) throw listed.error;
  const verified = listed.data.totp.find(f => f.status === "verified");
  if (verified) return { id: verified.id };
  const pending = listed.data.all.filter(f => f.factor_type === "totp" && f.status === "unverified");
  // Supabase cannot return an old QR/secret. Resume a previously scanned setup.
  // Replacing abandoned setup requires an explicit action and never removes verified factors.
  if (pending.length && !restart) return { id: pending[0].id, incomplete: true };
  for (const factor of pending) {
    const removed = await supabase.auth.mfa.unenroll({ factorId: factor.id });
    if (removed.error) throw removed.error;
  }
  const enrolled = await supabase.auth.mfa.enroll({ factorType: "totp", friendlyName: "Trifecta authenticator" });
  if (enrolled.error) throw enrolled.error;
  const raw = enrolled.data.totp.qr_code;
  const qr = raw.startsWith("data:")
    ? (raw.slice(0, raw.indexOf(",")).includes("base64") ? atob(raw.slice(raw.indexOf(",") + 1)) : decodeURIComponent(raw.slice(raw.indexOf(",") + 1)))
    : raw;
  return { id: enrolled.data.id, qr };
}
function initializeAuthenticator(userId: string, restart = false) {
  const existing = initializing.get(userId);
  if (existing) return existing;
  const request = prepareAuthenticator(restart).finally(() => initializing.delete(userId));
  initializing.set(userId, request);
  return request;
}

export function PrivilegedMfa({ userId, onVerified }: { userId: string; onVerified: () => void }) {
  const [authenticator, setAuthenticator] = useState<Authenticator | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [focused, setFocused] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const submitting = useRef(false);
  const input = useRef<TextInput>(null);
  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    void initializeAuthenticator(userId).then(value => {
      if (active) setAuthenticator(value);
    }).catch(() => {
      if (active) setError("We couldn’t load your authenticator. Check your connection and try again.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [userId, attempt]);

  async function restartSetup() {
    if (submitting.current) return;
    submitting.current = true; setBusy(true); setError(""); setCode("");
    try { setAuthenticator(await initializeAuthenticator(userId, true)); }
    catch { setError("Setup could not be restarted. Try again, or contact your administrator."); }
    finally { submitting.current = false; setBusy(false); }
  }
  async function verify() {
    if (!authenticator || !/^\d{6}$/.test(code) || submitting.current) return;
    submitting.current = true; setBusy(true); setError("");
    try {
      const result = await supabase.auth.mfa.challengeAndVerify({ factorId: authenticator.id, code });
      if (result.error) throw result.error;
      const assurance = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
      if (assurance.error || assurance.data.currentLevel !== "aal2") throw new Error("Assurance required");
      setCode(""); setAuthenticator(null); onVerified();
    } catch {
      setCode(""); setError("The code was rejected or expired. Enter the current six-digit code from your authenticator.");
      input.current?.focus();
    } finally { submitting.current = false; setBusy(false); }
  }
  const enrolling = !!authenticator?.qr;
  return <SafeAreaView style={styles.screen} edges={["top", "bottom", "left", "right"]}>
    <KeyboardAvoidingView style={styles.fill} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" automaticallyAdjustKeyboardInsets>
        <View style={styles.form}>
          <View style={styles.intro}>
            <Text accessibilityRole="header" style={styles.title}>{enrolling ? "Set up two-factor authentication" : "Verify your sign-in"}</Text>
            <Text style={styles.body}>{loading ? "Loading your authenticator…" : enrolling
              ? "Scan this QR code once with your authenticator app, then enter its six-digit code to finish setup. Keep the QR code private."
              : "Enter the six-digit code from your existing Trifecta authenticator to continue."}</Text>
          </View>
          {authenticator?.qr ? <View style={styles.qr} accessibilityLabel="Private authenticator enrollment QR code"><SvgXml xml={authenticator.qr} width={208} height={208} /></View> : null}
          {authenticator?.incomplete ? <Text style={styles.body}>You have an unfinished setup. If you already scanned its QR code, enter that code below. If you never scanned it, restart the unfinished setup.</Text> : null}
          <View style={styles.codeGroup}>
            <Text nativeID="authenticator-code-label" style={styles.label}>Authenticator code</Text>
            <TextInput ref={input} accessibilityLabel="Authenticator code" accessibilityLabelledBy="authenticator-code-label"
              accessibilityHint="Enter six digits from your authenticator app" aria-invalid={!!error}
              style={[styles.input, focused && styles.inputFocused, !!error && styles.inputError]}
              value={code} onChangeText={value => {
                setCode(value.replace(/[٠-٩]/g, digit => String(digit.charCodeAt(0) - 0x660)).replace(/[۰-۹]/g, digit => String(digit.charCodeAt(0) - 0x6f0)).replace(/\D/g, "").slice(0, 6));
                setError("");
              }}
              placeholder="000000" placeholderTextColor={colors.textSecondary} selectionColor={colors.primaryPressed}
              onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} editable={!!authenticator && !busy}
              keyboardType="number-pad" inputMode="numeric" autoComplete="one-time-code" textContentType="oneTimeCode"
              autoCorrect={false} autoCapitalize="none" returnKeyType="done" onSubmitEditing={() => void verify()} />
            <Text style={styles.hint}>Use the current code; it changes every 30 seconds.</Text>
          </View>
          {error ? <Text accessibilityRole="alert" style={uiStyles.error}>{error}</Text> : null}
          <AppButton title={busy ? "Verifying…" : enrolling ? "Complete setup" : "Verify code"} disabled={!authenticator || code.length !== 6 || busy || loading} loading={busy} onPress={() => void verify()} />
          {!authenticator && !loading ? <AppButton title="Try again" tone="secondary" onPress={() => setAttempt(value => value + 1)} /> : null}
          {authenticator?.incomplete ? <AppButton title="Restart unfinished setup" tone="secondary" disabled={busy} onPress={() => void restartSetup()} /> : null}
          <View style={styles.recovery}>
            <Text style={styles.recoveryTitle}>Lost your authenticator?</Text>
            <Text style={styles.hint}>Contact an authorized company administrator for identity-verified recovery. Email or a password reset alone cannot bypass this check.</Text>
          </View>
          <AppButton title="Sign out" tone="secondary" disabled={busy} onPress={() => void supabase.auth.signOut()} />
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  </SafeAreaView>;
}
const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  fill: { flex: 1 },
  content: { flexGrow: 1, justifyContent: "center", padding: spacing.lg, paddingVertical: spacing.xl },
  form: { width: "100%", maxWidth: 440, alignSelf: "center", backgroundColor: colors.surface, borderRadius: radii.md, padding: spacing.lg, gap: spacing.lg },
  intro: { gap: spacing.sm },
  title: { color: colors.text, fontSize: 26, lineHeight: 32, fontWeight: "700" },
  body: { color: colors.textSecondary, fontSize: 15, lineHeight: 22 },
  qr: { backgroundColor: "#FFFFFF", alignItems: "center", paddingVertical: spacing.sm },
  codeGroup: { gap: spacing.sm },
  label: { color: colors.text, fontSize: 16, fontWeight: "600" },
  input: { width: "100%", minHeight: 64, borderWidth: 2, borderColor: colors.textSecondary, borderRadius: radii.sm, backgroundColor: colors.surface, color: colors.text, fontSize: 28, fontWeight: "600", letterSpacing: 6, textAlign: "center", padding: spacing.md },
  inputFocused: { borderColor: colors.primaryPressed, backgroundColor: colors.surfaceElevated },
  inputError: { borderColor: colors.danger },
  hint: { color: colors.textSecondary, fontSize: 13, lineHeight: 20 },
  recovery: { gap: spacing.xs, paddingTop: spacing.lg, borderTopWidth: 1, borderTopColor: colors.border },
  recoveryTitle: { color: colors.text, fontSize: 14, fontWeight: "600" },
});

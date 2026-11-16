import { useEffect, useState } from "react";
import { ScrollView, Text, TextInput, View } from "react-native";
import { SvgXml } from "react-native-svg";
import { supabase } from "../lib";
import { AppButton } from "./ui";

export function PrivilegedMfa({ onVerified }: { onVerified: () => void }) {
  const [factor, setFactor] = useState("");
  const [qr, setQr] = useState("");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("Loading authenticator…");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    void (async () => {
      const listed = await supabase.auth.mfa.listFactors();
      if (listed.error) throw listed.error;
      const existing = listed.data.totp.find(f => f.status === "verified");
      if (existing) {
        if (active) { setFactor(existing.id); setMessage("Enter your authenticator code to continue."); }
        return;
      }
      // Only discard abandoned, unverified enrollments. Verified factors are never removed here.
      for (const pending of listed.data.all.filter(f => f.factor_type === "totp" && f.status === "unverified")) {
        const removed = await supabase.auth.mfa.unenroll({ factorId: pending.id });
        if (removed.error) throw removed.error;
      }
      const enrolled = await supabase.auth.mfa.enroll({ factorType: "totp", friendlyName: "Trifecta authenticator" });
      if (enrolled.error) throw enrolled.error;
      const raw = enrolled.data.totp.qr_code;
      const svg = raw.startsWith("data:") ? (raw.slice(0, raw.indexOf(",")).includes("base64") ? atob(raw.slice(raw.indexOf(",") + 1)) : decodeURIComponent(raw.slice(raw.indexOf(",") + 1))) : raw;
      if (active) { setFactor(enrolled.data.id); setQr(svg); setMessage("Scan this QR code with your authenticator app, then enter its six-digit code. Keep this QR code private."); }
    })().catch(() => { if (active) setMessage("Authenticator setup is unavailable. Sign out and try again."); });
    return () => { active = false; };
  }, []);
  async function verify() {
    if (!/^\d{6}$/.test(code) || busy) return;
    setBusy(true);
    try {
      const result = await supabase.auth.mfa.challengeAndVerify({ factorId: factor, code });
      if (result.error) throw result.error;
      setCode(""); setQr(""); onVerified();
    } catch { setCode(""); setMessage("The code was rejected or expired. Try the current code from your authenticator."); }
    finally { setBusy(false); }
  }
  return <ScrollView contentContainerStyle={{ padding: 24, gap: 16 }} keyboardShouldPersistTaps="handled">
    <Text accessibilityRole="header">Two-factor authentication required</Text>
    <Text>{message}</Text>
    {qr ? <View accessibilityLabel="Private authenticator enrollment QR code"><SvgXml xml={qr} width={240} height={240} /></View> : null}
    <TextInput accessibilityLabel="Authenticator code" value={code} onChangeText={v => setCode(v.replace(/\D/g, ""))} keyboardType="number-pad" autoComplete="one-time-code" maxLength={6} secureTextEntry />
    <AppButton title="Verify authenticator" disabled={!factor || code.length !== 6 || busy} loading={busy} onPress={() => void verify()} />
    <Text>Lost your authenticator? Contact an authorized company administrator for identity-verified recovery. Email or a password reset alone cannot bypass this check.</Text>
    <AppButton title="Sign out" onPress={() => void supabase.auth.signOut()} />
  </ScrollView>;
}

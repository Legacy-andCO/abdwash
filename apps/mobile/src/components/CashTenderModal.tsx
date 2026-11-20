import { useEffect, useState } from "react";
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as ImagePicker from "expo-image-picker";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import { getStaffLanguage, staffMoney, t } from "../i18n";
import { parseMoneyToMinor } from "../cash/cashTender";
import { colors, radii, spacing } from "../theme";
import { AppButton, uiStyles } from "./ui";

export function CashTenderModal({
  visible,
  dueMinor,
  currency,
  pending,
  onClose,
  onComplete,
}: {
  visible: boolean;
  dueMinor: number;
  currency: string;
  pending: boolean;
  onClose: () => void;
  onComplete: (
    received: number,
    change: number,
    method: "cash" | "card",
    reference: string,
    screenshot: string | null,
  ) => Promise<void>;
}) {
  const insets = useSafeAreaInsets();
  const inputStyle = [
    uiStyles.field,
    {
      textAlign:
        getStaffLanguage() === "ar" ? ("right" as const) : ("left" as const),
    },
  ];
  const [method, setMethod] = useState<"cash" | "card">("cash");
  const [received, setReceived] = useState("");
  const [reference, setReference] = useState("");
  const [proof, setProof] = useState<string | null>(null);
  const [imageError, setImageError] = useState("");
  const [picking, setPicking] = useState(false);
  useEffect(() => {
    if (visible) {
      setMethod("cash");
      setReceived("");
      setReference("");
      setProof(null);
      setImageError("");
    }
  }, [visible]);
  const amount = parseMoneyToMinor(received);
  const valid =
    amount !== null &&
    amount > 0 &&
    dueMinor > 0 &&
    (method === "cash" || amount <= dueMinor);
  const change = method === "cash" ? Math.max(0, (amount ?? 0) - dueMinor) : 0;
  const disabled = picking || pending;
  async function chooseProof() {
    setPicking(true);
    setImageError("");
    try {
      const selection = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"],
      });
      if (selection.canceled) return;
      const asset = selection.assets[0];
      const editor = ImageManipulator.manipulate(asset.uri);
      editor.resize({ width: Math.min(asset.width, 1200) });
      const rendered = await editor.renderAsync();
      const result = await rendered.saveAsync({
        format: SaveFormat.JPEG,
        compress: 0.72,
        base64: true,
      });
      if (!result.base64 || result.base64.length > 682664) throw new Error();
      setProof(result.base64);
    } catch {
      setImageError(t("Choose a smaller screenshot and try again."));
    } finally {
      setPicking(false);
    }
  }
  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={disabled ? undefined : onClose}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={[
          styles.backdrop,
          {
            paddingTop: insets.top,
            paddingLeft: insets.left,
            paddingRight: insets.right,
          },
        ]}
      >
        <ScrollView
          style={styles.sheet}
          contentContainerStyle={[
            styles.content,
            {
              paddingBottom: spacing.lg + insets.bottom,
              direction: getStaffLanguage() === "ar" ? "rtl" : "ltr",
            },
          ]}
          keyboardShouldPersistTaps="handled"
        >
          <Text accessibilityRole="header" style={styles.title}>
            {t("Receive payment")}
          </Text>
          <View>
            <Text style={uiStyles.label}>{t("Available to collect")}</Text>
            <Text style={styles.amount}>{staffMoney(dueMinor, currency)}</Text>
          </View>
          <View style={styles.methods}>
            {(["cash", "card"] as const).map((m) => (
              <Pressable
                key={m}
                disabled={disabled}
                accessibilityRole="radio"
                accessibilityState={{ checked: method === m }}
                style={[styles.choice, method === m && styles.active]}
                onPress={() => setMethod(m)}
              >
                <Text style={styles.choiceText}>
                  {t(m === "cash" ? "Cash" : "Card")}
                </Text>
              </Pressable>
            ))}
          </View>
          <View>
            <Text style={uiStyles.label}>
              {t("Money received")} · {currency}
            </Text>
            <TextInput
              style={inputStyle}
              accessibilityLabel={t("Money received")}
              editable={!disabled}
              maxLength={14}
              keyboardType="decimal-pad"
              value={received}
              onChangeText={setReceived}
              placeholder="0.00"
            />
            {received && !valid ? (
              <Text accessibilityRole="alert" style={uiStyles.error}>
                {t("Check the payment amount.")}
              </Text>
            ) : null}
          </View>
          {method === "card" ? (
            <>
              <TextInput
                autoCapitalize="none"
                autoCorrect={false}
                accessibilityLabel={t("Transaction reference (optional)")}
                placeholder={t("Transaction reference (optional)")}
                style={inputStyle}
                value={reference}
                onChangeText={setReference}
                maxLength={100}
                editable={!disabled}
              />
              <AppButton
                tone="secondary"
                disabled={disabled}
                title={t(
                  proof ? "Remove screenshot" : "Add screenshot (optional)",
                )}
                onPress={() => (proof ? setProof(null) : void chooseProof())}
              />
              <Text style={uiStyles.muted}>
                {t("Use a receipt with card details hidden.")}
              </Text>
              {imageError ? (
                <Text accessibilityRole="alert" style={uiStyles.error}>
                  {imageError}
                </Text>
              ) : null}
            </>
          ) : change > 0 ? (
            <Text style={uiStyles.body}>
              {t("CHANGE TO RETURN")} · {staffMoney(change, currency)}
            </Text>
          ) : null}
          <AppButton
            title={t("Submit for verification")}
            loading={pending}
            disabled={disabled || !valid}
            onPress={() =>
              void onComplete(
                amount!,
                change,
                method,
                method === "card" ? reference.trim() : "",
                method === "card" ? proof : null,
              )
            }
          />
          <AppButton
            title={t("Cancel")}
            tone="secondary"
            disabled={disabled}
            onPress={onClose}
          />
        </ScrollView>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(36,28,26,0.48)",
    justifyContent: "flex-end",
  },
  sheet: {
    width: "100%",
    maxWidth: 520,
    maxHeight: "96%",
    flexGrow: 0,
    alignSelf: "center",
    backgroundColor: colors.background,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
  },
  content: { padding: spacing.lg, gap: spacing.md },
  title: { color: colors.text, fontSize: 24, fontWeight: "900" },
  amount: { color: colors.text, fontSize: 30, fontWeight: "800" },
  methods: { flexDirection: "row", gap: spacing.sm },
  choice: {
    flex: 1,
    minHeight: 48,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
  },
  active: { backgroundColor: colors.secondary, borderColor: colors.primary },
  choiceText: { color: colors.text, fontWeight: "800" },
});

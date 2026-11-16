import { useId } from "react";
import { Modal, ScrollView, StyleSheet, Text, View } from "react-native";
import type { ReactNode } from "react";
import { colors, radii, spacing } from "../theme";
import { getStaffLanguage } from "../i18n";
import { AppButton } from "./ui";

export function ConfirmationModal({ visible, title, description, children, backLabel,
  confirmLabel, busy = false, disabled = false, backDisabled = false, confirmTone = "primary", onBack, onConfirm,
}: {
  visible: boolean; title: string; description: string; children?: ReactNode;
  backLabel: string; confirmLabel: string; busy?: boolean; disabled?: boolean; backDisabled?: boolean;
  confirmTone?: "primary" | "danger";
  onBack: () => void; onConfirm: () => void;
}) {
  const heading = useId();
  return <Modal transparent visible={visible} animationType="none" onRequestClose={() => { if (!busy && !backDisabled) onBack(); }}>
    <View style={[styles.backdrop, { direction: getStaffLanguage() === "ar" ? "rtl" : "ltr" }]}>
      <ScrollView style={styles.panel} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <View role="alertdialog" aria-modal accessibilityLabel={title} aria-labelledby={heading} accessibilityViewIsModal style={styles.body}>
          <Text nativeID={heading} accessibilityRole="header" style={styles.title}>{title}</Text>
          <Text style={styles.description}>{description}</Text>
          {children}
          <View style={styles.actions}>
            <AppButton title={backLabel} tone="secondary" disabled={busy || backDisabled} onPress={onBack} />
            <AppButton title={confirmLabel} tone={confirmTone} disabled={busy || disabled} loading={busy} onPress={onConfirm} />
          </View>
        </View>
      </ScrollView>
    </View>
  </Modal>;
}
const styles = StyleSheet.create({
  backdrop: { flex: 1, justifyContent: "center", alignItems: "center", padding: spacing.lg, backgroundColor: "rgba(36,28,26,0.55)" },
  panel: { flexGrow: 0, maxHeight: "90%", width: "100%", maxWidth: 460, borderRadius: radii.md, backgroundColor: colors.surface },
  content: { padding: spacing.xl },
  body: { gap: spacing.lg },
  title: { color: colors.text, fontSize: 24, fontWeight: "700", lineHeight: 30 },
  description: { color: colors.textSecondary, fontSize: 16, lineHeight: 24 },
  actions: { gap: spacing.md, paddingTop: spacing.sm },
});

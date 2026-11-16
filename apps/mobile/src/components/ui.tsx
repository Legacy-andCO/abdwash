import { useRef, useState, type ReactNode } from "react";
import type { StyleProp, ViewStyle } from "react-native";
import {
  Platform,
  ActivityIndicator,
  Animated,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { colors, radii, spacing } from "../theme";
import { buttonInteractionState } from "./buttonState";

export function ScreenTitle({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <View style={styles.titleWrap}>
      {eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}
      <Text accessibilityRole="header" style={styles.title}>{title}</Text>
      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
    </View>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

/** Inline secondary controls remain labelled and keyboard accessible. */
export function Disclosure({ title, children, initiallyOpen = false }: {
  title: string; children: ReactNode; initiallyOpen?: boolean;
}) {
  const [open, setOpen] = useState(initiallyOpen);
  return (
    <View style={styles.disclosure}>
      <Pressable accessibilityRole="button" accessibilityLabel={title} accessibilityState={{ expanded: open }} aria-expanded={open}
        onPress={() => setOpen(value => !value)} style={styles.disclosureToggle}>
        <Text style={styles.disclosureTitle}>{title}</Text>
        <Text style={styles.disclosureState}>{open ? "Hide" : "Show"}</Text>
      </Pressable>
      {open ? <View style={styles.disclosureBody}>{children}</View> : null}
    </View>
  );
}

export function AppButton({
  title,
  onPress,
  disabled,
  loading = false,
  tone = "primary",
}: {
  title: string;
  onPress: () => void;
  disabled?: boolean;
  loading?: boolean;
  tone?: "primary" | "secondary" | "danger";
}) {
  const scale = useRef(new Animated.Value(1)).current;
  const state = buttonInteractionState(disabled, loading);
  const backgroundColor =
    tone === "primary"
      ? colors.primaryPressed
      : tone === "danger"
        ? colors.dangerSurface
        : colors.secondary;
  const color =
    tone === "primary"
      ? colors.white
      : tone === "danger"
        ? colors.danger
        : colors.text;
  return (
    <Pressable
      accessibilityRole="button"
      disabled={state.disabled}
      accessibilityState={{ disabled: state.disabled, busy: state.busy }}
      onPressIn={() =>
        !disabled &&
        !loading &&
        Animated.spring(scale, { toValue: 0.98, useNativeDriver: true }).start()
      }
      onPressOut={() =>
        Animated.spring(scale, { toValue: 1, useNativeDriver: true }).start()
      }
      onPress={onPress}
    >
      <Animated.View
        style={[
          styles.button,
          {
            backgroundColor,
            transform: [{ scale }],
            opacity: disabled || loading ? 0.55 : 1,
          },
        ]}
      >
        <View style={styles.buttonContent}>
          {state.showSpinner ? <ActivityIndicator color={color} /> : null}
          <Text style={[styles.buttonText, { color }]}>{title}</Text>
        </View>
      </Animated.View>
    </Pressable>
  );
}

export function StatusChip({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const danger = normalized.includes("cancel") || normalized.includes("reject");
  const warning = normalized.includes("late") || normalized.includes("unpaid") || normalized.includes("pending") || normalized.includes("arrived") || normalized === "rescheduling_required";
  const active = normalized.includes("en_route") || normalized.includes("in_progress");
  const neutral = normalized.includes("assigned");
  return (
    <Text
      style={[
        styles.chip,
        danger ? styles.chipDanger : warning ? styles.chipWarning : active ? styles.chipActive : neutral ? styles.chipNeutral : undefined,
      ]}
    >
      {{ en_route: "On the way", in_progress: "Washing", rescheduling_required: "Needs reschedule", unpaid: "Payment due", assigned: "Scheduled" }[normalized] ?? value.replaceAll("_", " ").replace(/^./, letter => letter.toUpperCase())}
    </Text>
  );
}

export function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricValue}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body?: string;
  action?: ReactNode;
}) {
  return (
    <View style={styles.empty}>
      <Text style={styles.emptyTitle}>{title}</Text>
      {body ? <Text style={styles.subtitle}>{body}</Text> : null}
      {action}
    </View>
  );
}

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <View style={styles.skeletonWrap}>
      {Array.from({ length: rows }, (_, index) => (
        <View
          key={index}
          style={[styles.skeleton, { width: index % 2 ? "70%" : "100%" }]}
        />
      ))}
    </View>
  );
}

export const uiStyles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, gap: spacing.md, paddingBottom: 100 },
  row: {
    flexDirection: "row",
    ...(Platform.OS === "web" ? { flexWrap: "wrap" } as const : {}),
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  field: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    padding: 14,
    fontSize: 16,
    color: colors.text,
  },
  label: {
    fontSize: 12,
    fontWeight: "800",
    color: colors.textSecondary,
    letterSpacing: 0.6,
    marginBottom: 6,
  },
  body: { color: colors.text, fontSize: 15 },
  muted: { color: colors.textSecondary },
  link: {
    color: colors.primaryPressed,
    fontWeight: "800",
    paddingVertical: spacing.md,
    minHeight: 44,
  },
  error: {
    color: colors.danger,
    backgroundColor: colors.dangerSurface,
    padding: spacing.md,
    borderRadius: radii.sm,
  },
  success: {
    color: colors.success,
    backgroundColor: colors.successSurface,
    padding: spacing.md,
    borderRadius: radii.sm,
  },
});

const styles = StyleSheet.create({
  titleWrap: { gap: spacing.xs, marginBottom: spacing.sm },
  eyebrow: {
    fontSize: 11,
    fontWeight: "900",
    color: colors.primaryPressed,
    letterSpacing: 1.4,
  },
  title: {
    fontSize: 28,
    fontWeight: "700",
    color: colors.text,
    letterSpacing: -0.8,
  },
  subtitle: { color: colors.textSecondary, lineHeight: 20 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.lg,
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  button: {
    minHeight: 52,
    borderRadius: radii.md,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonText: { fontSize: 15, fontWeight: "700", textAlign: "center", flexShrink: 1 },
  buttonContent: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  chip: {
    color: colors.success,
    backgroundColor: colors.successSurface,
    paddingHorizontal: 9,
    paddingVertical: 6,
    borderRadius: radii.pill,
    fontWeight: "700",
    fontSize: 12,
    overflow: "hidden",
  },
  chipWarning: { color: colors.warning, backgroundColor: colors.warningSurface },
  chipDanger: { color: colors.danger, backgroundColor: colors.dangerSurface },
  chipActive: { color: colors.text, backgroundColor: colors.secondary },
  chipNeutral: { color: colors.textSecondary, backgroundColor: colors.neutralSurface },
  metric: {
    width: "48%",
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  metricValue: { fontSize: 22, fontWeight: "900", color: colors.text },
  metricLabel: { color: colors.textSecondary, marginTop: spacing.xs },
  empty: { alignItems: "center", padding: spacing.xxl, gap: spacing.sm },
  emptyTitle: { color: colors.text, fontSize: 18, fontWeight: "800" },
  skeletonWrap: { gap: spacing.md },
  skeleton: { height: 70, borderRadius: radii.lg, backgroundColor: colors.neutralSurface },
  disclosure: { borderTopWidth: 1, borderTopColor: colors.border },
  disclosureToggle: { minHeight: 52, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md },
  disclosureTitle: { color: colors.text, fontSize: 15, fontWeight: "600", flex: 1 },
  disclosureState: { color: colors.primaryPressed, fontSize: 14, fontWeight: "600" },
  disclosureBody: { gap: spacing.md, paddingBottom: spacing.md },
});

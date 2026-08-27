import { useEffect, useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  calculateCashTender,
  formatMoney,
  minorToInput,
} from "../cash/cashTender";
import { colors, radii, spacing } from "../theme";
import { AppButton, uiStyles } from "./ui";

const DENOMINATIONS_MINOR = [5_000, 10_000, 20_000, 50_000];

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
  onComplete: (tenderedMinor: number, changeMinor: number) => Promise<void>;
}) {
  const [received, setReceived] = useState("");
  useEffect(() => {
    if (visible) setReceived("");
  }, [visible, dueMinor]);
  const calculation = calculateCashTender(dueMinor, received);
  const denominations = DENOMINATIONS_MINOR.filter(
    (amount) => amount > dueMinor,
  );
  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={pending ? undefined : onClose}
    >
      <View style={styles.backdrop}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={styles.sheet}
        >
          <View style={uiStyles.row}>
            <View>
              <Text style={styles.title}>Receive payment</Text>
              <Text style={styles.cash}>CASH</Text>
            </View>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Close cash tender"
              disabled={pending}
              onPress={onClose}
            >
              <Text style={uiStyles.link}>Close</Text>
            </Pressable>
          </View>

          <View style={styles.amountPanel}>
            <Text style={styles.label}>AMOUNT DUE</Text>
            <Text style={styles.due}>{formatMoney(currency, dueMinor)}</Text>
          </View>

          <View>
            <Text style={uiStyles.label}>MONEY RECEIVED</Text>
            <View style={styles.moneyInputRow}>
              <Text style={styles.currency}>{currency}</Text>
              <TextInput
                accessibilityLabel="Money received"
                autoFocus
                editable={!pending}
                keyboardType="decimal-pad"
                placeholder="0.00"
                placeholderTextColor={colors.textSecondary}
                selectionColor={colors.primary}
                style={[uiStyles.field, styles.moneyInput]}
                value={received}
                onChangeText={setReceived}
              />
            </View>
          </View>

          <View style={styles.quickRow}>
            <QuickCash
              label="Exact"
              onPress={() => setReceived(minorToInput(dueMinor))}
            />
            {denominations.map((amount) => (
              <QuickCash
                key={amount}
                label={`${currency} ${amount / 100}`}
                onPress={() => setReceived(minorToInput(amount))}
              />
            ))}
          </View>

          {received && calculation.error ? (
            <Text accessibilityRole="alert" style={uiStyles.error}>
              {calculation.error}
            </Text>
          ) : null}

          <View style={styles.changePanel}>
            <Text style={styles.label}>CHANGE TO RETURN</Text>
            <Text style={styles.change}>
              {formatMoney(currency, calculation.changeMinor)}
            </Text>
          </View>

          <AppButton
            title={pending ? "Completing payment…" : "Complete payment"}
            loading={pending}
            disabled={pending || !calculation.valid}
            onPress={() =>
              void onComplete(
                calculation.tenderedMinor,
                calculation.changeMinor,
              )
            }
          />
          <AppButton
            title="Cancel"
            tone="secondary"
            disabled={pending}
            onPress={onClose}
          />
        </ScrollView>
      </View>
    </Modal>
  );
}

function QuickCash({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      style={styles.quick}
      onPress={onPress}
    >
      <Text style={styles.quickText}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(36, 28, 26, 0.48)",
  },
  sheet: {
    backgroundColor: colors.background,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    padding: spacing.xl,
    paddingBottom: 40,
    gap: spacing.lg,
  },
  title: { color: colors.text, fontSize: 25, fontWeight: "900" },
  cash: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 1.2,
  },
  amountPanel: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radii.lg,
    padding: spacing.lg,
    alignItems: "center",
  },
  label: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 1,
  },
  due: { color: colors.text, fontSize: 34, fontWeight: "900" },
  moneyInputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  currency: { color: colors.text, fontSize: 18, fontWeight: "900" },
  moneyInput: { flex: 1, fontSize: 24, fontWeight: "800" },
  quickRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  quick: {
    minHeight: 44,
    paddingHorizontal: spacing.md,
    justifyContent: "center",
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.primary,
    backgroundColor: colors.surface,
  },
  quickText: { color: colors.primary, fontWeight: "800" },
  changePanel: {
    alignItems: "center",
    borderRadius: radii.lg,
    backgroundColor: colors.secondary,
    padding: spacing.lg,
  },
  change: { color: colors.primaryPressed, fontSize: 30, fontWeight: "900" },
});

import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { operationalScope, queryKeys } from "../cache/policy";
import { AppButton, Card, EmptyState, ScreenTitle, Skeleton, uiStyles } from "../components/ui";
import { domainErrorMessage } from "../errors/domainErrors";
import { getStaffLanguage, staffLocale, t } from "../i18n";
import {
  getProductConsumption,
  saveProductConsumption,
  type InventoryItem,
  type ManagedService,
  type ProductConsumption,
  type StaffContext,
} from "../lib";
import { useManagedCatalogueQuery } from "../queries/operations";
import { colors, radii, spacing } from "../theme";

const smallerUnit: Record<string, string> = { liter: "milliliter", kilogram: "gram" };
const largerUnit: Record<string, string> = { milliliter: "liter", gram: "kilogram" };
const editableNumber = new Intl.NumberFormat("en", { useGrouping: false, maximumFractionDigits: 6 });

function normalizeRate(input: string) {
  return input.trim().replace(/[٠-٩۰-۹]/g, (digit) => String(digit.charCodeAt(0) & 15))
    .replace(/[٫,]/g, ".");
}

export function ProductConsumptionScreen({
  context, item, onBack,
}: {
  context: StaffContext;
  item: InventoryItem;
  onBack: () => void;
}) {
  const catalogue = useManagedCatalogueQuery(context);
  const queryKey = queryKeys.productConsumption(operationalScope(context), item.id);
  const rules = useQuery({ queryKey, queryFn: () => getProductConsumption(item.id) });
  const [selected, setSelected] = useState("");
  const services = (catalogue.data?.services ?? []).filter(
    (service) => service.is_active || rules.data?.some((rule) => rule.service_id === service.id),
  );
  const service = services.find((entry) => entry.id === selected) ?? services[0];
  const language = getStaffLanguage();

  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={[uiStyles.content, { direction: language === "ar" ? "rtl" : "ltr" }]}
    >
      <Pressable onPress={onBack} accessibilityRole="button">
        <Text style={uiStyles.link}>{t("Back to product")}</Text>
      </Pressable>
      <ScreenTitle title={t("Automatic consumption")} subtitle={item.name} />
      {catalogue.isError || rules.isError ? (
        <>
          <Text style={uiStyles.error}>{t("Consumption settings could not load.")}</Text>
          <AppButton title={t("Try again")} tone="secondary" onPress={() => {
            void catalogue.refetch();
            void rules.refetch();
          }} />
        </>
      ) : catalogue.isPending || rules.isPending ? (
        <Skeleton rows={5} />
      ) : service ? (
        <>
          <Text style={uiStyles.label}>{t("Service or package")}</Text>
          <View style={styles.choices}>
            {services.map((entry) => (
              <Choice key={entry.id} label={entry.name} selected={entry.id === service.id}
                onPress={() => setSelected(entry.id)} />
            ))}
          </View>
          <RateEditor
            key={service.id}
            item={item}
            service={service}
            categories={catalogue.data.vehicle_types}
            rules={rules.data.find((rule) => rule.service_id === service.id)}
            queryKey={queryKey}
          />
        </>
      ) : <EmptyState title={t("No services or packages available")} />}
    </ScrollView>
  );
}

function RateEditor({ item, service, categories, rules, queryKey }: {
  item: InventoryItem;
  service: ManagedService;
  categories: string[];
  rules?: ProductConsumption;
  queryKey: ReturnType<typeof queryKeys.productConsumption>;
}) {
  const client = useQueryClient();
  const [unit, setUnit] = useState(item.unit);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);
  const [invalid, setInvalid] = useState(false);
  const units = [item.unit, smallerUnit[item.unit] ?? largerUnit[item.unit]].filter(Boolean);
  const displayFactor = unit === item.unit ? 1 : unit === smallerUnit[item.unit] ? 1000 : 0.001;
  const rates = Object.fromEntries(Object.entries(rules?.rates ?? {}).map(
    ([category, value]) => [category, editableNumber.format(Number(value) * displayFactor)],
  ));
  const values = { ...rates, ...draft };
  const fallback = rules?.fallback == null ? null : new Intl.NumberFormat(staffLocale(), {
    maximumFractionDigits: 3,
  }).format(Number(rules.fallback));
  const mutation = useMutation({
    mutationFn: (next: Record<string, string>) =>
      saveProductConsumption(item.id, service.id, { unit, rates: next }),
    onSuccess: (updated) => {
      client.setQueryData<ProductConsumption[]>(queryKey, (previous = []) => [
        ...previous.filter((rule) => rule.service_id !== service.id), updated,
      ]);
      setDraft({});
      setSaved(true);
    },
  });

  function save() {
    const entered = Object.entries(values)
      .map(([category, value]) => [category, normalizeRate(value)] as const)
      .filter(([, value]) => value !== "");
    if (entered.some(([, value]) => !/^(?:\d+(?:\.\d{0,6})?|\.\d{1,6})$/.test(value))) {
      setInvalid(true);
      return;
    }
    mutation.mutate(Object.fromEntries(entered));
  }

  return (
    <Card style={styles.editor}>
      <Text accessibilityRole="header" style={styles.heading}>{t("Amount per vehicle")}</Text>
      <Text style={uiStyles.muted}>
        {fallback === null
          ? t("Leave blank if the rate is unknown. Enter 0 when this product is not used.")
          : t("Blank fields use the service rate of {amount} {unit}. Enter 0 to skip this product.",
            { amount: fallback, unit: t(item.unit) })}
      </Text>
      {units.length > 1 ? (
        <View style={styles.choices}>
          {units.map((choice) => (
            <Choice key={choice} label={t(choice)} selected={choice === unit}
              disabled={mutation.isPending || Object.keys(draft).length > 0}
              onPress={() => setUnit(choice)} />
          ))}
        </View>
      ) : <Text style={uiStyles.label}>{t(unit)}</Text>}
      {categories.map((category) => (
        <View key={category} style={styles.rate}>
          <Text style={styles.rateLabel}>{t(category === "suv" ? "SUV" : category)}</Text>
          <TextInput
            accessibilityLabel={t("{vehicle} amount in {unit}", { vehicle: t(category), unit: t(unit) })}
            editable={!mutation.isPending}
            keyboardType="decimal-pad"
            maxLength={18}
            placeholder="—"
            placeholderTextColor={colors.textSecondary}
            value={values[category] ?? ""}
            onChangeText={(value) => {
              setDraft((previous) => ({ ...previous, [category]: value }));
              setSaved(false);
              setInvalid(false);
              mutation.reset();
            }}
            style={[uiStyles.field, styles.amount]}
          />
        </View>
      ))}
      {invalid || mutation.isError ? (
        <Text accessibilityLiveRegion="polite" style={uiStyles.error}>
          {invalid ? t("Enter a valid non-negative amount.") :
            domainErrorMessage(mutation.error, "Consumption settings could not be saved.")}
        </Text>
      ) : null}
      {saved ? (
        <Text accessibilityLiveRegion="polite" style={uiStyles.body}>{t("Consumption settings saved.")}</Text>
      ) : null}
      <AppButton title={t("Save consumption")} onPress={save} loading={mutation.isPending}
        disabled={Object.keys(draft).length === 0} />
    </Card>
  );
}

function Choice({ label, selected, disabled, onPress }: {
  label: string; selected: boolean; disabled?: boolean; onPress: () => void;
}) {
  return (
    <Pressable accessibilityRole="button" accessibilityState={{ selected, disabled }}
      disabled={disabled} onPress={onPress}
      style={[styles.choice, selected && styles.selected, disabled && styles.disabled]}>
      <Text style={uiStyles.body}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  editor: { gap: spacing.sm },
  heading: { color: colors.text, fontSize: 17, fontWeight: "900" },
  choices: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
  choice: {
    maxWidth: "100%", minHeight: 44, justifyContent: "center",
    borderWidth: 1, borderColor: colors.border, borderRadius: radii.sm,
    paddingHorizontal: spacing.sm, paddingVertical: spacing.xs,
  },
  selected: { borderColor: colors.primary, backgroundColor: colors.secondary },
  disabled: { opacity: 0.6 },
  rate: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  rateLabel: { flex: 1, minWidth: 0, color: colors.text, fontSize: 14, fontWeight: "700", textTransform: "capitalize" },
  amount: { width: "44%", minWidth: 0, writingDirection: "ltr", textAlign: "center" },
});

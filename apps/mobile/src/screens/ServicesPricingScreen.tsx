import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  AppButton,
  Card,
  EmptyState,
  ScreenTitle,
  Skeleton,
  StatusChip,
  uiStyles,
} from "../components/ui";
import { domainErrorMessage } from "../errors/domainErrors";
import type {
  BusinessBookingSettings,
  CatalogueAddon,
  ManagedCatalogue,
  ManagedService,
  OperatingHour,
  StaffContext,
} from "../lib";
import {
  useBusinessSettingsQuery,
  useCatalogueMutation,
  useInventoryItemsQuery,
  useManagedCatalogueQuery,
  useServiceTemplateQuery,
} from "../queries/operations";
import { colors, radii, spacing } from "../theme";

type ManagementTab = "services" | "settings" | "consumables";
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export function ServicesPricingScreen({
  context,
  onBack,
}: {
  context: StaffContext;
  onBack: () => void;
}) {
  const management = context.role === "manager" || context.role === "admin";
  const [tab, setTab] = useState<ManagementTab>("services");
  const [editing, setEditing] = useState<ManagedService | "new" | null>(null);
  const catalogue = useManagedCatalogueQuery(context, management);
  const settings = useBusinessSettingsQuery(context, management && tab === "settings");
  const refreshing = catalogue.isRefetching || settings.isRefetching;

  if (!management) {
    return (
      <ScrollView contentContainerStyle={uiStyles.content}>
        <BackButton onPress={onBack} />
        <EmptyState title="Management access required" body="Only managers and admins can change catalogue settings." />
      </ScrollView>
    );
  }
  if (editing) {
    return (
      <ServiceEditor
        context={context}
        catalogue={catalogue.data ?? null}
        service={
          editing === "new"
            ? null
            : catalogue.data?.services.find((item) => item.id === editing.id) ?? editing
        }
        onBack={() => setEditing(null)}
      />
    );
  }
  async function refresh() {
    const requests: Promise<unknown>[] = [catalogue.refetch()];
    if (tab === "settings") requests.push(settings.refetch());
    await Promise.all(requests);
  }
  return (
    <ScrollView
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} />}
      contentContainerStyle={uiStyles.content}
    >
      <BackButton onPress={onBack} />
      <ScreenTitle title="Services & pricing" subtitle="The authoritative customer catalogue and booking rules" />
      <TabRow selected={tab} onSelect={setTab} />
      {catalogue.error || settings.error ? (
        <Text accessibilityRole="alert" style={uiStyles.error}>
          {domainErrorMessage(catalogue.error ?? settings.error, "Catalogue management could not load.")}
        </Text>
      ) : null}
      {catalogue.isPending ? (
        <Skeleton rows={4} />
      ) : tab === "services" ? (
        <ServicesList
          catalogue={catalogue.data ?? null}
          onCreate={() => setEditing("new")}
          onEdit={setEditing}
        />
      ) : tab === "settings" ? (
        settings.isPending ? <Skeleton rows={4} /> : (
          <SettingsEditor
            context={context}
            catalogue={catalogue.data ?? null}
            value={settings.data ?? null}
          />
        )
      ) : (
        <ConsumablesEditor context={context} catalogue={catalogue.data ?? null} />
      )}
    </ScrollView>
  );
}

function ServicesList({
  catalogue,
  onCreate,
  onEdit,
}: {
  catalogue: ManagedCatalogue | null;
  onCreate: () => void;
  onEdit: (service: ManagedService) => void;
}) {
  const services = catalogue?.services ?? [];
  const activeCount = services.filter((service) => service.is_active).length;
  const addonCount = services.reduce((total, service) => total + service.addons.length, 0);
  return (
    <>
      <View style={styles.summaryRow}>
        <Card style={styles.summaryCard}>
          <Text style={styles.price}>{activeCount}</Text>
          <Text style={uiStyles.muted}>Active services</Text>
        </Card>
        <Card style={styles.summaryCard}>
          <Text style={styles.price}>{addonCount}</Text>
          <Text style={uiStyles.muted}>Add-ons</Text>
        </Card>
      </View>
      <AppButton title="Add service" onPress={onCreate} />
      {!services.length ? (
        <EmptyState title="No services configured" body="Add the first bookable service." />
      ) : (
        services.map((service) => {
          const startingPrice = service.prices.reduce(
            (minimum, price) => Math.min(minimum, price.price_minor),
            Number.POSITIVE_INFINITY,
          );
          return (
            <Pressable key={service.id} accessibilityRole="button" onPress={() => onEdit(service)}>
              <Card>
                <View style={uiStyles.row}>
                  <View style={styles.flex}>
                    <Text style={styles.title}>{service.name}</Text>
                    <Text style={uiStyles.muted}>
                      {service.default_duration_minutes} min · Mobile service
                    </Text>
                  </View>
                  <StatusChip value={service.is_active ? "active" : "inactive"} />
                </View>
                <Text style={styles.price}>
                  {catalogue?.currency_code ?? "AED"} {Number.isFinite(startingPrice) ? (startingPrice / 100).toFixed(2) : "—"}
                </Text>
                <Text style={uiStyles.muted}>
                  {service.prices.length} vehicle prices · {service.addons.length} add-ons
                </Text>
                <Text style={uiStyles.body}>
                  {service.prices.slice(0, 3).map((price) =>
                    `${vehicleTypeLabel(price.vehicle_type)} ${(price.price_minor / 100).toFixed(2)}`,
                  ).join(" · ")}
                </Text>
                <Text style={uiStyles.link}>Edit service →</Text>
              </Card>
            </Pressable>
          );
        })
      )}
    </>
  );
}

function ServiceEditor({
  context,
  catalogue,
  service,
  onBack,
}: {
  context: StaffContext;
  catalogue: ManagedCatalogue | null;
  service: ManagedService | null;
  onBack: () => void;
}) {
  const mutation = useCatalogueMutation(context);
  const vehicleTypes = catalogue?.vehicle_types ?? [];
  const [name, setName] = useState(service?.name ?? "");
  const [description, setDescription] = useState(service?.description ?? "");
  const [hours, setHours] = useState(String(Math.floor((service?.default_duration_minutes ?? 120) / 60)));
  const [minutes, setMinutes] = useState(String((service?.default_duration_minutes ?? 120) % 60));
  const [sortOrder, setSortOrder] = useState(String(service?.sort_order ?? 0));
  const [prices, setPrices] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      vehicleTypes.map((type) => [
        type,
        service?.prices.find((price) => price.vehicle_type === type)
          ? String((service.prices.find((price) => price.vehicle_type === type)!.price_minor / 100).toFixed(2))
          : "",
      ]),
    ),
  );
  const [addon, setAddon] = useState<CatalogueAddon | "new" | null>(null);
  const duration = Number(hours) * 60 + Number(minutes);
  const validPrices = vehicleTypes.length > 0 && vehicleTypes.every((type) => moneyToMinor(prices[type]) !== null);
  const canSave =
    Boolean(name.trim()) &&
    duration >= 15 &&
    duration <= 1440 &&
    Number.isInteger(Number(sortOrder)) &&
    Number(sortOrder) >= 0 &&
    Number(sortOrder) <= 10_000 &&
    validPrices;

  async function save() {
    if (!canSave) return;
    const body = {
      name: name.trim(),
      description: description.trim() || null,
      default_duration_minutes: duration,
      mobile_available: true,
      ...(service ? {} : { shop_available: false }),
      sort_order: Number(sortOrder),
      prices: vehicleTypes.map((vehicle_type) => ({
        vehicle_type,
        price_minor: moneyToMinor(prices[vehicle_type])!,
      })),
    };
    try {
      await mutation.mutateAsync(
        service
          ? { action: "update_service", serviceId: service.id, body }
          : { action: "create_service", body },
      );
      Alert.alert("Service saved", "The customer catalogue now uses this configuration.");
      onBack();
    } catch (error) {
      Alert.alert("Service not saved", domainErrorMessage(error, "The server did not confirm this service."));
    }
  }
  async function toggleActive() {
    if (!service) return;
    try {
      await mutation.mutateAsync({
        action: "update_service",
        serviceId: service.id,
        body: { is_active: !service.is_active },
      });
      onBack();
    } catch (error) {
      Alert.alert("Service not updated", domainErrorMessage(error, "The server did not confirm this change."));
    }
  }
  if (addon && service) {
    return (
      <AddonEditor
        context={context}
        serviceId={service.id}
        addon={addon === "new" ? null : addon}
        onBack={() => setAddon(null)}
      />
    );
  }
  return (
    <ScrollView contentContainerStyle={uiStyles.content}>
      <BackButton label="Services" onPress={onBack} />
      <ScreenTitle title={service ? "Edit service" : "Add service"} subtitle="Prices are stored in minor currency units by the backend" />
      <Field label="Service name" value={name} onChange={setName} placeholder="Standard Wash" />
      <Field label="Description" value={description} onChange={setDescription} multiline />
      <Text style={uiStyles.label}>DEFAULT DURATION</Text>
      <View style={styles.durationRow}>
        <View style={styles.flex}><Field label="Hours" value={hours} onChange={setHours} keyboard="number-pad" /></View>
        <View style={styles.flex}><Field label="Minutes" value={minutes} onChange={setMinutes} keyboard="number-pad" /></View>
      </View>
      <Text style={uiStyles.muted}>Customer bookings are mobile service only.</Text>
      <Field label="Display order" value={sortOrder} onChange={setSortOrder} keyboard="number-pad" />
      <Text style={styles.section}>VEHICLE PRICING · {catalogue?.currency_code ?? "AED"}</Text>
      {vehicleTypes.map((type) => (
        <Field
          key={type}
          label={vehicleTypeLabel(type)}
          value={prices[type] ?? ""}
          onChange={(value) => setPrices((current) => ({ ...current, [type]: value }))}
          keyboard="decimal-pad"
          placeholder="0.00"
        />
      ))}
      <AppButton title="Save service" onPress={() => void save()} loading={mutation.isPending} disabled={!canSave} />
      {service ? (
        <>
          <Text style={styles.section}>ADD-ONS</Text>
          {service.addons.map((item) => (
            <Pressable key={item.id} accessibilityRole="button" onPress={() => setAddon(item)}>
              <Card>
                <View style={uiStyles.row}>
                  <View style={styles.flex}>
                    <Text style={styles.title}>{item.name}</Text>
                    <Text style={uiStyles.muted}>{catalogue?.currency_code} {(item.price_minor / 100).toFixed(2)}</Text>
                  </View>
                  <StatusChip value={item.is_active ? "active" : "inactive"} />
                </View>
              </Card>
            </Pressable>
          ))}
          <AppButton title="Add add-on" tone="secondary" onPress={() => setAddon("new")} />
          <AppButton
            title={service.is_active ? "Deactivate service" : "Reactivate service"}
            tone={service.is_active ? "danger" : "secondary"}
            onPress={() => void toggleActive()}
            loading={mutation.isPending}
          />
        </>
      ) : null}
    </ScrollView>
  );
}

function AddonEditor({
  context,
  serviceId,
  addon,
  onBack,
}: {
  context: StaffContext;
  serviceId: string;
  addon: CatalogueAddon | null;
  onBack: () => void;
}) {
  const mutation = useCatalogueMutation(context);
  const [name, setName] = useState(addon?.name ?? "");
  const [description, setDescription] = useState(addon?.description ?? "");
  const [price, setPrice] = useState(addon ? (addon.price_minor / 100).toFixed(2) : "");
  const [duration, setDuration] = useState(String(addon?.default_duration_minutes ?? 0));
  const canSave = Boolean(name.trim() && moneyToMinor(price) !== null && Number(duration) >= 0);
  async function save() {
    const body = {
      name: name.trim(),
      description: description.trim() || null,
      price_minor: moneyToMinor(price),
      default_duration_minutes: Number(duration),
      mobile_available: true,
      ...(addon ? {} : { shop_available: false }),
    };
    try {
      await mutation.mutateAsync(
        addon
          ? { action: "update_addon", addonId: addon.id, body }
          : { action: "create_addon", serviceId, body },
      );
      Alert.alert("Add-on saved", "The catalogue add-on is ready.");
      onBack();
    } catch (error) {
      Alert.alert("Add-on not saved", domainErrorMessage(error, "The server did not confirm this add-on."));
    }
  }
  async function toggleActive() {
    if (!addon) return;
    try {
      await mutation.mutateAsync({ action: "update_addon", addonId: addon.id, body: { is_active: !addon.is_active } });
      onBack();
    } catch (error) {
      Alert.alert("Add-on not updated", domainErrorMessage(error, "The server did not confirm this change."));
    }
  }
  return (
    <ScrollView contentContainerStyle={uiStyles.content}>
      <BackButton label="Service" onPress={onBack} />
      <ScreenTitle title={addon ? "Edit add-on" : "Add add-on"} subtitle="Optional extras can add price and expected time" />
      <Field label="Name" value={name} onChange={setName} />
      <Field label="Description" value={description} onChange={setDescription} multiline />
      <Field label="Price" value={price} onChange={setPrice} keyboard="decimal-pad" placeholder="0.00" />
      <Field label="Additional minutes" value={duration} onChange={setDuration} keyboard="number-pad" />
      <Text style={uiStyles.muted}>Available with mobile service bookings.</Text>
      <AppButton title="Save add-on" onPress={() => void save()} disabled={!canSave} loading={mutation.isPending} />
      {addon ? (
        <AppButton
          title={addon.is_active ? "Deactivate add-on" : "Reactivate add-on"}
          tone={addon.is_active ? "danger" : "secondary"}
          onPress={() => void toggleActive()}
          loading={mutation.isPending}
        />
      ) : null}
    </ScrollView>
  );
}

function SettingsEditor({
  context,
  catalogue,
  value,
}: {
  context: StaffContext;
  catalogue: ManagedCatalogue | null;
  value: BusinessBookingSettings | null;
}) {
  const mutation = useCatalogueMutation(context);
  const [draft, setDraft] = useState<BusinessBookingSettings | null>(value);
  useEffect(() => setDraft(value), [value]);
  if (!draft) return <EmptyState title="Settings unavailable" body="Pull down to try again." />;
  async function save() {
    if (!draft) return;
    try {
      await mutation.mutateAsync({
        action: "update_settings",
        body: {
          ...draft,
          operating_hours: draft.operating_hours.map((item) => ({
            ...item,
            opening_time: item.is_open ? item.opening_time : null,
            closing_time: item.is_open ? item.closing_time : null,
          })),
        },
      });
      Alert.alert("Settings saved", "Future availability and bookings use these rules.");
    } catch (error) {
      Alert.alert("Settings not saved", domainErrorMessage(error, "The server did not confirm these settings."));
    }
  }
  const updateHour = (weekday: number, patch: Partial<OperatingHour>) =>
    setDraft((current) => current ? {
      ...current,
      operating_hours: current.operating_hours.map((item) => item.weekday === weekday ? { ...item, ...patch } : item),
    } : current);
  return (
    <>
      <Text style={styles.section}>BOOKING GRID</Text>
      <Text style={uiStyles.label}>SLOT DURATION</Text>
      <ChoiceRow
        values={[60, 90, 120].map((minutes) => ({ id: String(minutes), label: `${minutes} min` }))}
        selected={String(draft.slot_duration_minutes)}
        onSelect={(selected) => setDraft({ ...draft, slot_duration_minutes: Number(selected) })}
      />
      <Field
        label="Cancellation cutoff (hours)"
        value={String(draft.cancellation_cutoff_hours)}
        onChange={(selected) => setDraft({ ...draft, cancellation_cutoff_hours: Number(selected) })}
        keyboard="number-pad"
      />
      <Toggle
        label="Mobile booking minimum"
        value={draft.mobile_minimum_enabled}
        onChange={(selected) => setDraft({ ...draft, mobile_minimum_enabled: selected })}
      />
      {draft.mobile_minimum_enabled ? (
        <Field
          label={`Minimum (${draft.currency_code})`}
          value={(draft.mobile_minimum_minor / 100).toFixed(2)}
          onChange={(selected) => setDraft({ ...draft, mobile_minimum_minor: moneyToMinor(selected) ?? 0 })}
          keyboard="decimal-pad"
        />
      ) : null}
      <Field
        label="Default time between mobile jobs (minutes)"
        value={String(draft.default_team_turnaround_minutes)}
        onChange={(selected) => setDraft({ ...draft, default_team_turnaround_minutes: Number(selected) })}
        keyboard="number-pad"
      />
      <Text style={uiStyles.muted}>Automatic assignment uses this buffer between a team's mobile jobs.</Text>
      <Text style={styles.section}>LOYALTY REWARD SERVICE</Text>
      <ChoiceRow
        values={[{ id: "", label: "None" }, ...(catalogue?.services.filter((item) => item.is_active).map((item) => ({ id: item.id, label: item.name })) ?? [])]}
        selected={draft.loyalty_reward_service_id ?? ""}
        onSelect={(selected) => setDraft({ ...draft, loyalty_reward_service_id: selected || null })}
      />
      <Text style={styles.section}>OPERATING HOURS</Text>
      {draft.operating_hours.map((item) => (
        <Card key={item.weekday}>
          <Toggle label={DAYS[item.weekday] ?? `Day ${item.weekday}`} value={item.is_open} onChange={(selected) => updateHour(item.weekday, { is_open: selected })} />
          {item.is_open ? (
            <View style={styles.durationRow}>
              <View style={styles.flex}>
                <Field label="Opens" value={(item.opening_time ?? "08:00").slice(0, 5)} onChange={(selected) => updateHour(item.weekday, { opening_time: selected })} placeholder="08:00" />
              </View>
              <View style={styles.flex}>
                <Field label="Closes" value={(item.closing_time ?? "18:00").slice(0, 5)} onChange={(selected) => updateHour(item.weekday, { closing_time: selected })} placeholder="18:00" />
              </View>
            </View>
          ) : null}
        </Card>
      ))}
      <AppButton title="Save business settings" onPress={() => void save()} loading={mutation.isPending} />
    </>
  );
}

function ConsumablesEditor({ context, catalogue }: { context: StaffContext; catalogue: ManagedCatalogue | null }) {
  const mutation = useCatalogueMutation(context);
  const [serviceId, setServiceId] = useState(catalogue?.services[0]?.id ?? "");
  const template = useServiceTemplateQuery(context, serviceId, Boolean(serviceId));
  const items = useInventoryItemsQuery(context, "", 0, true);
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  useEffect(() => {
    setQuantities(Object.fromEntries((template.data ?? []).map((line) => [line.item_id, String(line.expected_quantity)])));
  }, [template.data]);
  const selectedLines = useMemo(
    () => Object.entries(quantities).filter(([, quantity]) => Number(quantity) > 0),
    [quantities],
  );
  async function save() {
    try {
      await mutation.mutateAsync({
        action: "update_template",
        serviceId,
        body: { lines: selectedLines.map(([item_id, expected_quantity]) => ({ item_id, expected_quantity: Number(expected_quantity) })) },
      });
      Alert.alert(
        "Template saved",
        "The current expected quantities will be snapshotted when future jobs complete.",
      );
    } catch (error) {
      Alert.alert("Template not saved", domainErrorMessage(error, "The server did not confirm this template."));
    }
  }
  if (!catalogue?.services.length) return <EmptyState title="No services available" />;
  return (
    <>
      <Text style={uiStyles.muted}>
        Expected usage per completed service is snapshotted when the job completes. These quantities are estimates, not exact physical usage.
      </Text>
      <Text style={uiStyles.label}>SERVICE</Text>
      <ChoiceRow values={catalogue.services.map((service) => ({ id: service.id, label: service.name }))} selected={serviceId} onSelect={setServiceId} />
      {template.error || items.error ? <Text style={uiStyles.error}>{domainErrorMessage(template.error ?? items.error, "Consumables could not load.")}</Text> : null}
      {template.isPending || items.isPending ? <Skeleton rows={3} /> : (items.data?.items ?? []).map((item) => (
        <Field
          key={item.id}
          label={`${item.name} (${item.unit})${item.is_active ? "" : " — inactive; remove before saving"}`}
          value={quantities[item.id] ?? ""}
          onChange={(selected) => setQuantities((current) => ({ ...current, [item.id]: selected }))}
          keyboard="decimal-pad"
          placeholder="Not used"
        />
      ))}
      <AppButton title="Save consumption template" onPress={() => void save()} disabled={!serviceId} loading={mutation.isPending} />
    </>
  );
}

function TabRow({ selected, onSelect }: { selected: ManagementTab; onSelect: (tab: ManagementTab) => void }) {
  return (
    <View style={styles.tabs}>
      {(["services", "settings", "consumables"] as const).map((tab) => (
        <Pressable
          key={tab}
          accessibilityRole="tab"
          accessibilityState={{ selected: selected === tab }}
          onPress={() => onSelect(tab)}
          style={[styles.tab, selected === tab ? styles.tabActive : undefined]}
        >
          <Text style={[styles.tabText, selected === tab ? styles.tabTextActive : undefined]}>{tab.toUpperCase()}</Text>
        </Pressable>
      ))}
    </View>
  );
}

function ChoiceRow({ values, selected, onSelect }: { values: { id: string; label: string }[]; selected: string; onSelect: (value: string) => void }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.choices}>
      {values.map((value) => (
        <Pressable
          key={value.id || "none"}
          accessibilityRole="button"
          accessibilityState={{ selected: selected === value.id }}
          onPress={() => onSelect(value.id)}
          style={[styles.choice, selected === value.id ? styles.choiceActive : undefined]}
        >
          <Text style={[styles.choiceText, selected === value.id ? styles.choiceTextActive : undefined]}>{value.label}</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (value: boolean) => void }) {
  return (
    <View style={styles.toggle}>
      <Text style={styles.toggleLabel}>{label}</Text>
      <Switch accessibilityLabel={label} value={value} onValueChange={onChange} trackColor={{ false: colors.border, true: colors.accent }} thumbColor={value ? colors.primary : colors.surface} />
    </View>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  keyboard = "default",
  multiline = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  keyboard?: "default" | "decimal-pad" | "number-pad";
  multiline?: boolean;
}) {
  return (
    <View>
      <Text style={uiStyles.label}>{label.toUpperCase()}</Text>
      <TextInput
        accessibilityLabel={label}
        value={value}
        onChangeText={onChange}
        placeholder={placeholder}
        placeholderTextColor={colors.textSecondary}
        keyboardType={keyboard}
        multiline={multiline}
        style={[uiStyles.field, multiline ? styles.multiline : undefined]}
      />
    </View>
  );
}

function BackButton({ label = "Management", onPress }: { label?: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress}>
      <Text style={uiStyles.link}>← {label}</Text>
    </Pressable>
  );
}

function moneyToMinor(value: string | undefined) {
  if (value === undefined || value.trim() === "") return null;
  const amount = Number(value);
  if (!Number.isFinite(amount) || amount < 0) return null;
  return Math.round(amount * 100);
}

function vehicleTypeLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  title: { color: colors.text, fontSize: 17, fontWeight: "900" },
  price: { color: colors.text, fontSize: 22, fontWeight: "900" },
  section: { color: colors.primary, fontSize: 12, fontWeight: "900", letterSpacing: 1.1, marginTop: spacing.md },
  tabs: { flexDirection: "row", gap: spacing.xs },
  tab: { flex: 1, paddingVertical: spacing.md, alignItems: "center", borderBottomWidth: 2, borderBottomColor: colors.border },
  tabActive: { borderBottomColor: colors.primary },
  tabText: { color: colors.textSecondary, fontWeight: "800", fontSize: 10 },
  tabTextActive: { color: colors.primary },
  durationRow: { flexDirection: "row", gap: spacing.sm },
  toggle: { minHeight: 52, paddingHorizontal: spacing.md, flexDirection: "row", alignItems: "center", justifyContent: "space-between", borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface, borderRadius: radii.md },
  toggleLabel: { color: colors.text, fontWeight: "800", flex: 1 },
  choices: { gap: spacing.sm, paddingBottom: spacing.xs },
  choice: { borderWidth: 1, borderColor: colors.border, borderRadius: radii.md, paddingHorizontal: spacing.md, paddingVertical: spacing.sm, backgroundColor: colors.surface },
  choiceActive: { borderColor: colors.primary, backgroundColor: colors.secondary },
  choiceText: { color: colors.textSecondary },
  choiceTextActive: { color: colors.primary, fontWeight: "900" },
  multiline: { minHeight: 96, textAlignVertical: "top" },
  summaryRow: { flexDirection: "row", gap: spacing.sm },
  summaryCard: { flex: 1 },
});

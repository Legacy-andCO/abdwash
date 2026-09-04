import { useState } from "react";
import {
  Alert,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";

import { AppButton, Card, EmptyState, Skeleton, StatusChip, uiStyles } from "../components/ui";
import { domainErrorMessage } from "../errors/domainErrors";
import type { Coupon, CouponWrite, ManagedCatalogue, StaffContext } from "../lib";
import { useCouponMutation, useCouponsQuery } from "../queries/operations";
import { colors, radii, spacing } from "../theme";

export function CouponManager({
  context,
  catalogue,
}: {
  context: StaffContext;
  catalogue: ManagedCatalogue | null;
}) {
  const coupons = useCouponsQuery(context);
  const mutation = useCouponMutation(context);
  const [editing, setEditing] = useState<Coupon | "new" | null>(null);

  if (editing) {
    return (
      <CouponEditor
        catalogue={catalogue}
        coupon={editing === "new" ? null : editing}
        loading={mutation.isPending}
        onCancel={() => setEditing(null)}
        onSave={async (body) => {
          try {
            await mutation.mutateAsync(
              editing === "new"
                ? { action: "create", body }
                : { action: "update", couponId: editing.id, body },
            );
            Alert.alert("Coupon saved", "New checkouts now use this coupon configuration.");
            setEditing(null);
          } catch (error) {
            Alert.alert(
              "Coupon not saved",
              domainErrorMessage(error, "The server did not confirm this coupon."),
            );
          }
        }}
      />
    );
  }

  if (coupons.isPending) return <Skeleton rows={4} />;
  if (coupons.error) {
    return (
      <Text accessibilityRole="alert" style={uiStyles.error}>
        {domainErrorMessage(coupons.error, "Coupons could not load.")}
      </Text>
    );
  }
  const items = coupons.data?.coupons ?? [];
  return (
    <>
      <Text style={uiStyles.muted}>
        Coupons discount one eligible booking service line. Confirmed bookings keep their saved
        discount if a coupon changes later.
      </Text>
      <AppButton title="Create coupon" onPress={() => setEditing("new")} />
      {!items.length ? (
        <EmptyState title="No coupons" body="Create the first checkout coupon." />
      ) : (
        items.map((coupon) => (
          <Pressable
            accessibilityRole="button"
            key={coupon.id}
            onPress={() => setEditing(coupon)}
          >
            <Card>
              <View style={uiStyles.row}>
                <View style={styles.flex}>
                  <Text style={styles.code}>{coupon.code}</Text>
                  <Text style={styles.discount}>{coupon.discount_percent}% OFF</Text>
                </View>
                <StatusChip value={coupon.is_active ? "active" : "inactive"} />
              </View>
              <Text style={uiStyles.muted}>
                {coupon.services.map((service) => service.name).join(" · ")}
              </Text>
              <Text style={uiStyles.muted}>
                {coupon.vehicle_types.map(vehicleTypeLabel).join(" · ")} · {minimumLabel(coupon)}
              </Text>
              <Text style={uiStyles.link}>Edit coupon →</Text>
            </Card>
          </Pressable>
        ))
      )}
    </>
  );
}

function CouponEditor({
  catalogue,
  coupon,
  loading,
  onCancel,
  onSave,
}: {
  catalogue: ManagedCatalogue | null;
  coupon: Coupon | null;
  loading: boolean;
  onCancel: () => void;
  onSave: (body: CouponWrite) => Promise<void>;
}) {
  const [code, setCode] = useState(coupon?.code ?? "");
  const [discount, setDiscount] = useState(String(coupon?.discount_percent ?? ""));
  const [minimum, setMinimum] = useState(String(coupon?.minimum_vehicle_count ?? ""));
  const [vehicleTypes, setVehicleTypes] = useState(
    () => new Set(coupon?.vehicle_types ?? []),
  );
  const [serviceIds, setServiceIds] = useState(
    () => new Set(coupon?.services.map((service) => service.id) ?? []),
  );
  const [active, setActive] = useState(coupon?.is_active ?? true);
  const percentage = Number(discount);
  const minimumCount = minimum === "" ? null : Number(minimum);
  const valid =
    /^[A-Z0-9]{3,6}$/.test(code) &&
    Number.isInteger(percentage) &&
    percentage >= 1 &&
    percentage <= 100 &&
    (minimumCount === null ||
      (Number.isInteger(minimumCount) && minimumCount >= 1 && minimumCount <= 20)) &&
    vehicleTypes.size > 0 &&
    serviceIds.size > 0;

  const toggle = (current: Set<string>, value: string, update: (next: Set<string>) => void) => {
    const next = new Set(current);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    update(next);
  };

  return (
    <>
      <Pressable accessibilityRole="button" onPress={onCancel}>
        <Text style={uiStyles.link}>← Coupons</Text>
      </Pressable>
      <Text style={styles.heading}>{coupon ? "Edit coupon" : "Create coupon"}</Text>
      <Field
        label="Coupon code"
        value={code}
        maxLength={6}
        onChange={(value) =>
          setCode(value.replace(/[^A-Za-z0-9]/g, "").toUpperCase().slice(0, 6))
        }
        placeholder="VIP20"
      />
      <Text style={uiStyles.muted}>3–6 letters or numbers. Codes are saved in uppercase.</Text>
      <Field
        keyboard="number-pad"
        label="Discount percent"
        onChange={setDiscount}
        placeholder="20"
        value={discount}
      />
      <Field
        keyboard="number-pad"
        label="Minimum vehicles (optional)"
        onChange={setMinimum}
        placeholder="No minimum"
        value={minimum}
      />
      <Text style={styles.section}>ELIGIBLE VEHICLE TYPES</Text>
      {(catalogue?.vehicle_types ?? []).map((vehicleType) => (
        <CheckRow
          checked={vehicleTypes.has(vehicleType)}
          key={vehicleType}
          label={vehicleTypeLabel(vehicleType)}
          onPress={() => toggle(vehicleTypes, vehicleType, setVehicleTypes)}
        />
      ))}
      <Text style={styles.section}>ELIGIBLE SERVICES</Text>
      {(catalogue?.services ?? [])
        .filter((service) => service.is_active)
        .map((service) => (
          <CheckRow
            checked={serviceIds.has(service.id)}
            key={service.id}
            label={service.name}
            onPress={() => toggle(serviceIds, service.id, setServiceIds)}
          />
        ))}
      <View style={styles.toggle}>
        <Text style={styles.toggleLabel}>Active</Text>
        <Switch
          accessibilityLabel="Active"
          onValueChange={setActive}
          thumbColor={active ? colors.primary : colors.surface}
          trackColor={{ false: colors.border, true: colors.accent }}
          value={active}
        />
      </View>
      <AppButton
        disabled={!valid}
        loading={loading}
        onPress={() =>
          void onSave({
            code,
            discount_percent: percentage,
            minimum_vehicle_count: minimumCount,
            service_ids: [...serviceIds],
            vehicle_types: [...vehicleTypes],
            is_active: active,
          })
        }
        title="Save coupon"
      />
    </>
  );
}

function CheckRow({
  checked,
  label,
  onPress,
}: {
  checked: boolean;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      onPress={onPress}
      style={[styles.checkRow, checked ? styles.checkRowActive : undefined]}
    >
      <Text style={styles.check}>{checked ? "✓" : ""}</Text>
      <Text style={styles.checkLabel}>{label}</Text>
    </Pressable>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  keyboard = "default",
  maxLength,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  keyboard?: "default" | "number-pad";
  maxLength?: number;
}) {
  return (
    <View>
      <Text style={uiStyles.label}>{label.toUpperCase()}</Text>
      <TextInput
        accessibilityLabel={label}
        autoCapitalize={label === "Coupon code" ? "characters" : "none"}
        keyboardType={keyboard}
        maxLength={maxLength}
        onChangeText={onChange}
        placeholder={placeholder}
        placeholderTextColor={colors.textSecondary}
        style={uiStyles.field}
        value={value}
      />
    </View>
  );
}

function minimumLabel(coupon: Coupon) {
  return coupon.minimum_vehicle_count
    ? `${coupon.minimum_vehicle_count}+ vehicles`
    : "No minimum";
}

function vehicleTypeLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  code: { color: colors.text, fontSize: 18, fontWeight: "900", letterSpacing: 1.2 },
  discount: { color: colors.primary, fontSize: 13, fontWeight: "900" },
  heading: { color: colors.text, fontSize: 25, fontWeight: "900" },
  section: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 1.1,
    marginTop: spacing.md,
  },
  checkRow: {
    alignItems: "center",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.md,
    borderWidth: 1,
    flexDirection: "row",
    gap: spacing.sm,
    minHeight: 50,
    paddingHorizontal: spacing.md,
  },
  checkRowActive: { backgroundColor: colors.secondary, borderColor: colors.primary },
  check: {
    borderColor: colors.primary,
    borderRadius: 5,
    borderWidth: 1,
    color: colors.primary,
    fontWeight: "900",
    height: 22,
    textAlign: "center",
    width: 22,
  },
  checkLabel: { color: colors.text, flex: 1, fontWeight: "700" },
  toggle: {
    alignItems: "center",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.md,
    borderWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    minHeight: 52,
    paddingHorizontal: spacing.md,
  },
  toggleLabel: { color: colors.text, fontWeight: "800" },
});

import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";

import { shouldShowPagination } from "../cache/policy";
import { capabilities } from "../capabilities";
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
import { successHaptic } from "../haptics";
import { ClientEventIdStore } from "../idempotency/clientEventId";
import type {
  CustomerAddress,
  CustomerVehicle,
  ManagerCustomerDetail,
  ManagerCustomerListItem,
  StaffContext,
} from "../lib";
import {
  useLoyaltyAdjustmentMutation,
  useLoyaltySettingsQuery,
  useManagerAddressMutation,
  useManagerCustomerQuery,
  useManagerCustomersQuery,
  useManagerVehicleMutation,
  useServiceOptionsQuery,
  useUpdateLoyaltySettingsMutation,
  useUpdateManagerCustomerMutation,
} from "../queries/operations";
import { colors, radii, spacing } from "../theme";

export function CustomersScreen({
  context,
  onBack,
  onOpenJob,
}: {
  context: StaffContext;
  onBack: () => void;
  onOpenJob: (jobId: string) => void;
}) {
  const [searchText, setSearchText] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(" ".concat(searchText).trim().replace(/\s+/g, " "));
      setOffset(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchText]);
  const query = useManagerCustomersQuery(context, search, offset);
  if (!capabilities(context.role).canManageCustomers)
    return (
      <EmptyState
        title="Customers unavailable"
        body="Manager access is required."
      />
    );
  if (selectedId)
    return (
      <CustomerDetailScreen
        context={context}
        customerId={selectedId}
        onBack={() => setSelectedId(null)}
        onOpenJob={onOpenJob}
      />
    );
  return (
    <ScrollView
      refreshControl={
        <RefreshControl
          refreshing={query.isRefetching}
          onRefresh={() => void query.refetch()}
        />
      }
      contentContainerStyle={uiStyles.content}
    >
      <Pressable accessibilityRole="button" onPress={onBack}>
        <Text style={uiStyles.link}>← Today</Text>
      </Pressable>
      <View style={uiStyles.row}>
        <ScreenTitle
          title="Customers"
          subtitle="Profiles, saved details and loyalty"
        />
        <Pressable
          accessibilityRole="button"
          onPress={() => setSettingsOpen(true)}
        >
          <Text style={uiStyles.link}>Loyalty settings</Text>
        </Pressable>
      </View>
      <TextInput
        accessibilityLabel="Search customers"
        autoCapitalize="none"
        autoCorrect={false}
        placeholder="Search name, phone, email or plate"
        placeholderTextColor={colors.textSecondary}
        selectionColor={colors.primary}
        style={uiStyles.field}
        value={searchText}
        onChangeText={setSearchText}
      />
      {query.isPending ? (
        <Skeleton rows={5} />
      ) : query.isError ? (
        <EmptyState
          title="Customers unavailable"
          body={domainErrorMessage(query.error, "We couldn't load customers.")}
          action={
            <AppButton title="Try again" onPress={() => void query.refetch()} />
          }
        />
      ) : query.data?.customers.length ? (
        <>
          {query.data.customers.map((customer) => (
            <CustomerCard
              key={customer.id}
              customer={customer}
              onPress={() => setSelectedId(customer.id)}
            />
          ))}
          {shouldShowPagination(offset, query.data.next_offset) ? (
            <View style={styles.buttonRow}>
              <View style={styles.flex}>
                <AppButton
                  title="Previous"
                  tone="secondary"
                  disabled={offset === 0}
                  onPress={() => setOffset(Math.max(0, offset - 30))}
                />
              </View>
              <View style={styles.flex}>
                <AppButton
                  title="Next"
                  tone="secondary"
                  disabled={query.data.next_offset === null}
                  onPress={() => setOffset(query.data?.next_offset ?? offset)}
                />
              </View>
            </View>
          ) : null}
        </>
      ) : (
        <EmptyState
          title="No customers found"
          body="Try another name, phone, email address or plate number."
        />
      )}
      <LoyaltySettingsModal
        context={context}
        visible={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
    </ScrollView>
  );
}

function CustomerCard({
  customer,
  onPress,
}: {
  customer: ManagerCustomerListItem;
  onPress: () => void;
}) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress}>
      <Card>
        <View style={uiStyles.row}>
          <Text style={styles.title}>
            {customer.first_name} {customer.surname}
          </Text>
          {customer.available_rewards ? (
            <StatusChip
              value={`${customer.available_rewards} reward available`}
            />
          ) : null}
        </View>
        <Text style={uiStyles.body}>{customer.phone}</Text>
        <Text style={uiStyles.muted}>
          {customer.active_vehicle_count} vehicle
          {customer.active_vehicle_count === 1 ? "" : "s"} ·{" "}
          {customer.booking_count} bookings
        </Text>
        <Text style={uiStyles.muted}>
          Loyalty {customer.loyalty_progress_washes} /{" "}
          {customer.loyalty_required_washes}
        </Text>
        <Text style={uiStyles.muted}>
          Last visit:{" "}
          {customer.latest_booking_at
            ? new Date(customer.latest_booking_at).toLocaleDateString()
            : "No bookings yet"}
        </Text>
      </Card>
    </Pressable>
  );
}

function CustomerDetailScreen({
  context,
  customerId,
  onBack,
  onOpenJob,
}: {
  context: StaffContext;
  customerId: string;
  onBack: () => void;
  onOpenJob: (jobId: string) => void;
}) {
  const [historyOffset, setHistoryOffset] = useState(0);
  const query = useManagerCustomerQuery(context, customerId, historyOffset);
  const [profileOpen, setProfileOpen] = useState(false);
  const [addressTarget, setAddressTarget] = useState<
    CustomerAddress | "new" | null
  >(null);
  const [vehicleTarget, setVehicleTarget] = useState<
    CustomerVehicle | "new" | null
  >(null);
  const [adjustOpen, setAdjustOpen] = useState(false);
  const value = query.data;
  return (
    <ScrollView
      refreshControl={
        <RefreshControl
          refreshing={query.isRefetching}
          onRefresh={() => void query.refetch()}
        />
      }
      contentContainerStyle={uiStyles.content}
    >
      <Pressable accessibilityRole="button" onPress={onBack}>
        <Text style={uiStyles.link}>← Customers</Text>
      </Pressable>
      {query.isPending ? (
        <Skeleton rows={6} />
      ) : query.isError || !value ? (
        <EmptyState
          title="Customer unavailable"
          body={domainErrorMessage(
            query.error,
            "We couldn't load this customer.",
          )}
          action={
            <AppButton title="Try again" onPress={() => void query.refetch()} />
          }
        />
      ) : (
        <>
          <ScreenTitle
            title={`${value.profile.first_name} ${value.profile.surname}`}
            subtitle={value.profile.phone}
          />
          <Card>
            <View style={uiStyles.row}>
              <Text style={styles.section}>CUSTOMER</Text>
              <Pressable
                accessibilityRole="button"
                onPress={() => setProfileOpen(true)}
              >
                <Text style={uiStyles.link}>Edit</Text>
              </Pressable>
            </View>
            <Text style={uiStyles.body}>{value.profile.phone}</Text>
            <Text style={uiStyles.muted}>
              {value.profile.email} · email read-only
            </Text>
          </Card>
          <Card>
            <View style={uiStyles.row}>
              <Text style={styles.section}>LOYALTY</Text>
              <Pressable
                accessibilityRole="button"
                onPress={() => setAdjustOpen(true)}
              >
                <Text style={uiStyles.link}>Adjust loyalty</Text>
              </Pressable>
            </View>
            <Text style={styles.rewardMetric}>
              {value.loyalty.progress_washes} / {value.loyalty.required_washes}{" "}
              washes
            </Text>
            <Text style={uiStyles.muted}>
              {value.loyalty.washes_remaining} remaining ·{" "}
              {value.loyalty.available_rewards} available rewards
            </Text>
            <Text style={uiStyles.muted}>
              Lifetime qualifying washes{" "}
              {value.loyalty.lifetime_qualifying_washes} · Redeemed{" "}
              {value.loyalty.redeemed_rewards}
            </Text>
            {value.loyalty.history.slice(0, 8).map((item) => (
              <View key={item.id} style={styles.historyRow}>
                <Text style={uiStyles.body}>
                  {item.event_type.replaceAll("_", " ")}
                </Text>
                <Text style={uiStyles.muted}>
                  {item.quantity > 0 ? "+" : ""}
                  {item.quantity} ·{" "}
                  {new Date(item.created_at).toLocaleDateString()}
                </Text>
                {item.reason ? (
                  <Text style={uiStyles.muted}>{item.reason}</Text>
                ) : null}
              </View>
            ))}
          </Card>
          <DetailSection
            title="VEHICLES"
            action="Add vehicle"
            onAction={() => setVehicleTarget("new")}
          >
            {value.vehicles.length ? (
              value.vehicles.map((item) => (
                <ManageableRow
                  key={item.id}
                  title={`${item.make} ${item.model}`}
                  detail={`Plate ${item.plate_number ?? "—"} · ${item.vehicle_type}`}
                  onEdit={() => setVehicleTarget(item)}
                />
              ))
            ) : (
              <Text style={uiStyles.muted}>No saved vehicles.</Text>
            )}
          </DetailSection>
          <DetailSection
            title="LOCATIONS"
            action="Add location"
            onAction={() => setAddressTarget("new")}
          >
            {value.addresses.length ? (
              value.addresses.map((item) => (
                <ManageableRow
                  key={item.id}
                  title={`${item.label}${item.is_default ? " · Default" : ""}`}
                  detail={item.written_address}
                  onEdit={() => setAddressTarget(item)}
                />
              ))
            ) : (
              <Text style={uiStyles.muted}>No saved locations.</Text>
            )}
          </DetailSection>
          <BookingHistory
            value={value}
            offset={historyOffset}
            onOffsetChange={setHistoryOffset}
            onOpenJob={onOpenJob}
          />
          <ProfileEditModal
            context={context}
            detail={value}
            visible={profileOpen}
            onClose={() => setProfileOpen(false)}
          />
          <AddressEditModal
            context={context}
            customerId={customerId}
            target={addressTarget}
            onClose={() => setAddressTarget(null)}
          />
          <VehicleEditModal
            context={context}
            customerId={customerId}
            target={vehicleTarget}
            onClose={() => setVehicleTarget(null)}
          />
          <LoyaltyAdjustmentModal
            context={context}
            customerId={customerId}
            visible={adjustOpen}
            onClose={() => setAdjustOpen(false)}
          />
        </>
      )}
    </ScrollView>
  );
}

function DetailSection({
  title,
  action,
  onAction,
  children,
}: {
  title: string;
  action: string;
  onAction: () => void;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <View style={uiStyles.row}>
        <Text style={styles.section}>{title}</Text>
        <Pressable accessibilityRole="button" onPress={onAction}>
          <Text style={uiStyles.link}>{action}</Text>
        </Pressable>
      </View>
      {children}
    </Card>
  );
}

function ManageableRow({
  title,
  detail,
  onEdit,
}: {
  title: string;
  detail: string;
  onEdit: () => void;
}) {
  return (
    <View style={styles.manageRow}>
      <View style={styles.flex}>
        <Text style={styles.itemTitle}>{title}</Text>
        <Text style={uiStyles.muted}>{detail}</Text>
      </View>
      <Pressable accessibilityRole="button" onPress={onEdit}>
        <Text style={uiStyles.link}>Edit</Text>
      </Pressable>
    </View>
  );
}

function BookingHistory({
  value,
  offset,
  onOffsetChange,
  onOpenJob,
}: {
  value: ManagerCustomerDetail;
  offset: number;
  onOffsetChange: (offset: number) => void;
  onOpenJob: (jobId: string) => void;
}) {
  const now = Date.now();
  const upcoming = value.bookings.filter(
    (item) =>
      Date.parse(item.scheduled_start) >= now && item.status !== "cancelled",
  );
  const history = value.bookings.filter((item) => !upcoming.includes(item));
  return (
    <Card>
      <Text style={styles.section}>UPCOMING BOOKINGS</Text>
      {upcoming.length ? (
        upcoming.map((item) => (
          <BookingRow key={item.id} item={item} onOpenJob={onOpenJob} />
        ))
      ) : (
        <Text style={uiStyles.muted}>No upcoming bookings.</Text>
      )}
      <Text style={styles.section}>HISTORY</Text>
      {history.length ? (
        history.map((item) => (
          <BookingRow key={item.id} item={item} onOpenJob={onOpenJob} />
        ))
      ) : (
        <Text style={uiStyles.muted}>No booking history.</Text>
      )}
      {offset > 0 || value.bookings_next_offset !== null ? (
        <View style={styles.buttonRow}>
          <View style={styles.flex}>
            <AppButton
              title="Newer"
              tone="secondary"
              disabled={offset === 0}
              onPress={() => onOffsetChange(Math.max(0, offset - 30))}
            />
          </View>
          <View style={styles.flex}>
            <AppButton
              title="Older"
              tone="secondary"
              disabled={value.bookings_next_offset === null}
              onPress={() =>
                onOffsetChange(value.bookings_next_offset ?? offset)
              }
            />
          </View>
        </View>
      ) : null}
    </Card>
  );
}

function BookingRow({
  item,
  onOpenJob,
}: {
  item: ManagerCustomerDetail["bookings"][number];
  onOpenJob: (jobId: string) => void;
}) {
  const content = (
    <>
      <View style={uiStyles.row}>
        <Text style={styles.itemTitle}>{item.reference}</Text>
        <StatusChip value={item.job_status ?? item.status} />
      </View>
      {item.vehicles.map((vehicle, index) => (
        <Text
          key={`${vehicle.make}-${vehicle.model}-${index}`}
          style={uiStyles.body}
        >
          {vehicle.make} {vehicle.model} · {vehicle.plate_number ?? "No plate"}
          {vehicle.service_name ? ` · ${vehicle.service_name}` : ""}
        </Text>
      ))}
      <Text style={uiStyles.muted}>
        {new Date(item.scheduled_start).toLocaleString()} · {item.currency_code}{" "}
        {(item.total_amount_minor / 100).toFixed(2)} · {item.payment_status}
      </Text>
      {item.complaint_count ? (
        <Text style={uiStyles.muted}>
          {item.complaint_count} quality complaint
          {item.complaint_count === 1 ? "" : "s"}
        </Text>
      ) : null}
    </>
  );
  return item.job_id ? (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`Open job ${item.reference}`}
      style={styles.historyRow}
      onPress={() => onOpenJob(item.job_id!)}
    >
      {content}
    </Pressable>
  ) : (
    <View style={styles.historyRow}>{content}</View>
  );
}

function Sheet({
  visible,
  title,
  onClose,
  children,
}: {
  visible: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <Modal
      transparent
      visible={visible}
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={styles.sheet}
        >
          <View style={uiStyles.row}>
            <Text style={styles.sheetTitle}>{title}</Text>
            <Pressable onPress={onClose}>
              <Text style={uiStyles.link}>Close</Text>
            </Pressable>
          </View>
          {children}
        </ScrollView>
      </View>
    </Modal>
  );
}

function Field({
  label,
  value,
  onChangeText,
  ...props
}: {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
} & Omit<React.ComponentProps<typeof TextInput>, "value" | "onChangeText">) {
  return (
    <View>
      <Text style={uiStyles.label}>{label}</Text>
      <TextInput
        {...props}
        placeholderTextColor={colors.textSecondary}
        selectionColor={colors.primary}
        style={[uiStyles.field, props.multiline ? styles.multiline : undefined]}
        value={value}
        onChangeText={onChangeText}
      />
    </View>
  );
}

function ProfileEditModal({
  context,
  detail,
  visible,
  onClose,
}: {
  context: StaffContext;
  detail: ManagerCustomerDetail;
  visible: boolean;
  onClose: () => void;
}) {
  const mutation = useUpdateManagerCustomerMutation(context, detail.profile.id);
  const [firstName, setFirstName] = useState(detail.profile.first_name);
  const [surname, setSurname] = useState(detail.profile.surname);
  const [phone, setPhone] = useState(detail.profile.phone);
  useEffect(() => {
    if (visible) {
      setFirstName(detail.profile.first_name);
      setSurname(detail.profile.surname);
      setPhone(detail.profile.phone);
    }
  }, [
    detail.profile.first_name,
    detail.profile.phone,
    detail.profile.surname,
    visible,
  ]);
  async function save() {
    try {
      await mutation.mutateAsync({ first_name: firstName, surname, phone });
      await successHaptic();
      onClose();
    } catch (error) {
      Alert.alert(
        "Customer not saved",
        domainErrorMessage(error, "Review the customer details and try again."),
      );
    }
  }
  return (
    <Sheet visible={visible} title="Edit customer" onClose={onClose}>
      <Field label="FIRST NAME" value={firstName} onChangeText={setFirstName} />
      <Field label="SURNAME" value={surname} onChangeText={setSurname} />
      <Field
        label="PHONE"
        keyboardType="phone-pad"
        value={phone}
        onChangeText={setPhone}
      />
      <Field
        label="EMAIL (READ ONLY)"
        editable={false}
        value={detail.profile.email}
        onChangeText={() => undefined}
      />
      <AppButton
        title={mutation.isPending ? "Saving…" : "Save changes"}
        disabled={
          mutation.isPending ||
          !firstName.trim() ||
          !surname.trim() ||
          !phone.trim()
        }
        loading={mutation.isPending}
        onPress={() => void save()}
      />
    </Sheet>
  );
}

function AddressEditModal({
  context,
  customerId,
  target,
  onClose,
}: {
  context: StaffContext;
  customerId: string;
  target: CustomerAddress | "new" | null;
  onClose: () => void;
}) {
  const mutation = useManagerAddressMutation(context, customerId);
  const existing = target === "new" || target === null ? null : target;
  const [label, setLabel] = useState("");
  const [address, setAddress] = useState("");
  const [url, setUrl] = useState("");
  const [instructions, setInstructions] = useState("");
  const [isDefault, setDefault] = useState(false);
  useEffect(() => {
    if (target) {
      const value = target === "new" ? null : target;
      setLabel(value?.label ?? "");
      setAddress(value?.written_address ?? "");
      setUrl(value?.location_url ?? "");
      setInstructions(value?.location_instructions ?? "");
      setDefault(value?.is_default ?? false);
    }
  }, [target]);
  async function save() {
    try {
      await mutation.mutateAsync({
        action: existing ? "update" : "create",
        id: existing?.id,
        body: {
          label,
          written_address: address,
          location_url: url,
          latitude:
            existing && url.trim() === existing.location_url
              ? existing.latitude
              : null,
          longitude:
            existing && url.trim() === existing.location_url
              ? existing.longitude
              : null,
          instructions,
          is_default: isDefault,
        },
      });
      await successHaptic();
      onClose();
    } catch (error) {
      Alert.alert(
        "Location not saved",
        domainErrorMessage(error, "Review the saved location and try again."),
      );
    }
  }
  function remove() {
    if (!existing) return;
    Alert.alert("Remove saved location?", existing.label, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Remove",
        style: "destructive",
        onPress: async () => {
          try {
            await mutation.mutateAsync({ action: "delete", id: existing.id });
            onClose();
          } catch (error) {
            Alert.alert(
              "Location not removed",
              domainErrorMessage(error, "Try again."),
            );
          }
        },
      },
    ]);
  }
  return (
    <Sheet
      visible={target !== null}
      title={existing ? "Edit location" : "Add location"}
      onClose={onClose}
    >
      <Field label="LABEL" value={label} onChangeText={setLabel} />
      <Field
        label="ADDRESS"
        multiline
        value={address}
        onChangeText={setAddress}
      />
      <Field
        label="GOOGLE MAPS LINK"
        autoCapitalize="none"
        keyboardType="url"
        value={url}
        onChangeText={setUrl}
      />
      <Field
        label="LOCATION INSTRUCTIONS"
        multiline
        value={instructions}
        onChangeText={setInstructions}
      />
      <View style={uiStyles.row}>
        <Text style={uiStyles.body}>Default location</Text>
        <Switch
          value={isDefault}
          onValueChange={setDefault}
          trackColor={{ true: colors.primary }}
        />
      </View>
      <AppButton
        title={mutation.isPending ? "Saving…" : "Save location"}
        loading={mutation.isPending}
        disabled={
          mutation.isPending ||
          !label.trim() ||
          !address.trim() ||
          !url.trim() ||
          !instructions.trim()
        }
        onPress={() => void save()}
      />
      {existing ? (
        <AppButton
          title="Remove location"
          tone="danger"
          disabled={mutation.isPending}
          onPress={remove}
        />
      ) : null}
    </Sheet>
  );
}

function VehicleEditModal({
  context,
  customerId,
  target,
  onClose,
}: {
  context: StaffContext;
  customerId: string;
  target: CustomerVehicle | "new" | null;
  onClose: () => void;
}) {
  const mutation = useManagerVehicleMutation(context, customerId);
  const existing = target === "new" || target === null ? null : target;
  const [make, setMake] = useState("");
  const [model, setModel] = useState("");
  const [year, setYear] = useState("");
  const [type, setType] = useState("");
  const [colour, setColour] = useState("");
  const [plate, setPlate] = useState("");
  const [notes, setNotes] = useState("");
  useEffect(() => {
    if (target) {
      const value = target === "new" ? null : target;
      setMake(value?.make ?? "");
      setModel(value?.model ?? "");
      setYear(value?.year ? String(value.year) : "");
      setType(value?.vehicle_type ?? "");
      setColour(value?.colour ?? "");
      setPlate(value?.plate_number ?? "");
      setNotes(value?.notes ?? "");
    }
  }, [target]);
  async function save() {
    try {
      await mutation.mutateAsync({
        action: existing ? "update" : "create",
        id: existing?.id,
        body: {
          make,
          model,
          year: year ? Number(year) : null,
          vehicle_type: type,
          colour: colour || null,
          plate_number: plate,
          notes: notes || null,
        },
      });
      await successHaptic();
      onClose();
    } catch (error) {
      Alert.alert(
        "Vehicle not saved",
        domainErrorMessage(error, "Review the vehicle details and try again."),
      );
    }
  }
  function remove() {
    if (!existing) return;
    Alert.alert("Remove saved vehicle?", `${existing.make} ${existing.model}`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Remove",
        style: "destructive",
        onPress: async () => {
          try {
            await mutation.mutateAsync({ action: "delete", id: existing.id });
            onClose();
          } catch (error) {
            Alert.alert(
              "Vehicle not removed",
              domainErrorMessage(error, "Try again."),
            );
          }
        },
      },
    ]);
  }
  return (
    <Sheet
      visible={target !== null}
      title={existing ? "Edit vehicle" : "Add vehicle"}
      onClose={onClose}
    >
      <Field label="MAKE" value={make} onChangeText={setMake} />
      <Field label="MODEL" value={model} onChangeText={setModel} />
      <Field
        label="YEAR"
        keyboardType="number-pad"
        value={year}
        onChangeText={setYear}
      />
      <Field label="VEHICLE TYPE" value={type} onChangeText={setType} />
      <Field label="COLOUR" value={colour} onChangeText={setColour} />
      <Field
        label="PLATE NUMBER"
        autoCapitalize="characters"
        value={plate}
        onChangeText={setPlate}
      />
      <Field label="NOTES" multiline value={notes} onChangeText={setNotes} />
      <AppButton
        title={mutation.isPending ? "Saving…" : "Save vehicle"}
        loading={mutation.isPending}
        disabled={
          mutation.isPending ||
          !make.trim() ||
          !model.trim() ||
          !type.trim() ||
          !plate.trim()
        }
        onPress={() => void save()}
      />
      {existing ? (
        <AppButton
          title="Remove vehicle"
          tone="danger"
          disabled={mutation.isPending}
          onPress={remove}
        />
      ) : null}
    </Sheet>
  );
}

function LoyaltyAdjustmentModal({
  context,
  customerId,
  visible,
  onClose,
}: {
  context: StaffContext;
  customerId: string;
  visible: boolean;
  onClose: () => void;
}) {
  const mutation = useLoyaltyAdjustmentMutation(context, customerId);
  const eventIds = useRef(new ClientEventIdStore()).current;
  const [direction, setDirection] = useState<"credit" | "debit">("credit");
  const [washes, setWashes] = useState("1");
  const [reason, setReason] = useState("");
  useEffect(() => {
    if (visible) {
      setDirection("credit");
      setWashes("1");
      setReason("");
    }
  }, [visible]);
  async function submit() {
    const key = `${customerId}:${direction}:${washes}:${reason.trim()}`;
    try {
      await mutation.mutateAsync({
        direction,
        washes: Number(washes),
        reason: reason.trim(),
        client_event_id: eventIds.get(key),
      });
      eventIds.succeeded(key);
      await successHaptic();
      onClose();
    } catch (error) {
      eventIds.failed(key, error);
      Alert.alert(
        "Loyalty not adjusted",
        domainErrorMessage(error, "Review the adjustment and try again."),
      );
    }
  }
  return (
    <Sheet visible={visible} title="Adjust loyalty" onClose={onClose}>
      <View style={styles.buttonRow}>
        <View style={styles.flex}>
          <AppButton
            title="Add wash credit"
            tone={direction === "credit" ? "primary" : "secondary"}
            onPress={() => setDirection("credit")}
          />
        </View>
        <View style={styles.flex}>
          <AppButton
            title="Remove wash credit"
            tone={direction === "debit" ? "primary" : "secondary"}
            onPress={() => setDirection("debit")}
          />
        </View>
      </View>
      <Field
        label="AMOUNT"
        keyboardType="number-pad"
        value={washes}
        onChangeText={setWashes}
      />
      <Field label="REASON" multiline value={reason} onChangeText={setReason} />
      <AppButton
        title={mutation.isPending ? "Saving adjustment…" : "Save adjustment"}
        loading={mutation.isPending}
        disabled={mutation.isPending || Number(washes) < 1 || !reason.trim()}
        onPress={() => void submit()}
      />
    </Sheet>
  );
}

function LoyaltySettingsModal({
  context,
  visible,
  onClose,
}: {
  context: StaffContext;
  visible: boolean;
  onClose: () => void;
}) {
  const query = useLoyaltySettingsQuery(context);
  const services = useServiceOptionsQuery();
  const mutation = useUpdateLoyaltySettingsMutation(context);
  const [enabled, setEnabled] = useState(true);
  const [required, setRequired] = useState("9");
  const [serviceId, setServiceId] = useState<string | null>(null);
  useEffect(() => {
    if (visible && query.data) {
      setEnabled(query.data.enabled);
      setRequired(String(query.data.required_washes));
      setServiceId(query.data.reward_service?.id ?? null);
    }
  }, [query.data, visible]);
  async function save() {
    try {
      await mutation.mutateAsync({
        enabled,
        required_washes: Number(required),
        reward_service_id: serviceId,
      });
      await successHaptic();
      onClose();
    } catch (error) {
      Alert.alert(
        "Loyalty settings not saved",
        domainErrorMessage(
          error,
          "Review the loyalty configuration and try again.",
        ),
      );
    }
  }
  return (
    <Sheet visible={visible} title="Loyalty settings" onClose={onClose}>
      {query.isPending || services.isPending ? (
        <Skeleton rows={3} />
      ) : (
        <>
          <View style={uiStyles.row}>
            <Text style={uiStyles.body}>Loyalty enabled</Text>
            <Switch
              value={enabled}
              onValueChange={setEnabled}
              trackColor={{ true: colors.primary }}
            />
          </View>
          <Field
            label="WASHES REQUIRED"
            keyboardType="number-pad"
            value={required}
            onChangeText={setRequired}
          />
          <Text style={uiStyles.label}>REWARD SERVICE</Text>
          {services.data?.map((service) => (
            <Pressable
              key={service.id}
              accessibilityRole="radio"
              accessibilityState={{ checked: serviceId === service.id }}
              style={[
                styles.choice,
                serviceId === service.id ? styles.choiceActive : undefined,
              ]}
              onPress={() => setServiceId(service.id)}
            >
              <Text style={styles.itemTitle}>{service.name}</Text>
              <Text style={uiStyles.muted}>
                {service.currency_code} {(service.price_minor / 100).toFixed(2)}
              </Text>
            </Pressable>
          ))}
          <AppButton
            title={mutation.isPending ? "Saving…" : "Save settings"}
            loading={mutation.isPending}
            disabled={
              mutation.isPending ||
              Number(required) < 1 ||
              (enabled && !serviceId)
            }
            onPress={() => void save()}
          />
        </>
      )}
    </Sheet>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  title: { color: colors.text, fontSize: 18, fontWeight: "900", flexShrink: 1 },
  section: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 1.1,
  },
  itemTitle: { color: colors.text, fontSize: 16, fontWeight: "800" },
  rewardMetric: { color: colors.primary, fontSize: 25, fontWeight: "900" },
  buttonRow: { flexDirection: "row", gap: spacing.sm },
  manageRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingVertical: spacing.sm,
  },
  historyRow: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.sm,
    gap: spacing.xs,
  },
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
    gap: spacing.md,
  },
  sheetTitle: { color: colors.text, fontSize: 24, fontWeight: "900" },
  multiline: { minHeight: 88, textAlignVertical: "top" },
  choice: {
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.md,
  },
  choiceActive: {
    borderColor: colors.primary,
    backgroundColor: colors.secondary,
  },
});

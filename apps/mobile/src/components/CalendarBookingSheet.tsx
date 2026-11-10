import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Linking, Modal, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { Alert } from "../alert";
import { operationalScope } from "../cache/policy";
import { domainErrorMessage } from "../errors/domainErrors";
import { isUncertainMutationFailure, newClientEventId } from "../idempotency/clientEventId";
import { api, type CalendarJob, type StaffContext } from "../lib";
import { colors, spacing } from "../theme";
import { formatUaeDateTime, formatWallClockTime, UAE_TIME_ZONE, uaeDateKey, wallDate } from "../time/uaeTime";
import { DatePickerField } from "./pickers";
import { AppButton, Card, uiStyles } from "./ui";
import { webSheetStyle } from "./webSheetStyle";

const path = "/api/v1/staff/calendar-bookings";
const policyLinks = {
  "terms-and-conditions": "Terms & Conditions",
  "cancellation-and-refund-policy": "Cancellation & Refund Policy",
  "privacy-policy": "Privacy Policy",
};

type Service = {
  id: string;
  name: string;
  customer_bookable: boolean;
  prices: { vehicle_type: string; price_minor: number }[];
};
type Catalogue = {
  services: Service[];
  settings: { currency_code: string };
  policy_revision: string;
  public_web_url: string | null;
};
type Availability = {
  slots: { time: string; available: boolean }[];
};
type VehicleInput = {
  make: string;
  model: string;
  plate_number: string;
  service_id: string;
  vehicle_type: string;
};
type BookingReceipt = {
  job_id: string;
  reference: string;
  scheduled_start: string;
  replaced_appointment: boolean;
};

function newVehicle(): VehicleInput {
  return { make: "", model: "", plate_number: "", service_id: "", vehicle_type: "" };
}

function Entry({
  label, value, onChange, multiline = false, keyboardType = "default",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
  keyboardType?: "default" | "phone-pad" | "email-address" | "numbers-and-punctuation";
}) {
  return (
    <View>
      <Text style={uiStyles.label}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        style={uiStyles.field}
        value={value}
        onChangeText={onChange}
        multiline={multiline}
        keyboardType={keyboardType}
        autoCapitalize={keyboardType === "email-address" ? "none" : "sentences"}
      />
    </View>
  );
}

export function CalendarBookingSheet({
  context, initialDate, replacement, onClose, onBooked,
}: {
  context: StaffContext;
  initialDate: string;
  replacement: CalendarJob | null;
  onClose: () => void;
  onBooked: (jobId: string, date: string) => void;
}) {
  const [day, setDay] = useState(replacement?.local_date ?? initialDate);
  const [start, setStart] = useState(() => replacement
    ? new Intl.DateTimeFormat("en-GB", {
        timeZone: UAE_TIME_ZONE, hourCycle: "h23", hour: "2-digit", minute: "2-digit", second: "2-digit",
      }).format(new Date(replacement.scheduled_start))
    : "");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");
  const [notes, setNotes] = useState("");
  const [vehicles, setVehicles] = useState([newVehicle()]);
  const [showGps, setShowGps] = useState(false);
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [reason, setReason] = useState("");
  const [delivery, setDelivery] = useState<"provided" | "email" | null>(null);
  const [language, setLanguage] = useState<"en" | "ar">("en");
  const [review, setReview] = useState(false);
  const [receipt, setReceipt] = useState<BookingReceipt | null>(null);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState("");
  const attempt = useRef<{ key: string; body: string } | null>(null);
  const submitting = useRef(false);
  const scope = operationalScope(context);
  const catalogue = useQuery({
    queryKey: ["calendar-booking-catalogue", scope],
    queryFn: ({ signal }) => api<Catalogue>(`${path}/catalogue`, { signal }),
    refetchOnMount: "always",
  });
  const services = (catalogue.data?.services ?? []).filter((service) => service.customer_bookable);
  const serviceIds = vehicles.map((vehicle) => vehicle.service_id);
  const availability = useQuery({
    queryKey: ["calendar-booking-availability", scope, day, serviceIds],
    queryFn: ({ signal }) => {
      const query = new URLSearchParams({ date: day });
      serviceIds.forEach((id) => query.append("service_id", id));
      return api<Availability>(`${path}/availability?${query}`, { signal });
    },
    enabled: !replacement && serviceIds.every(Boolean),
  });
  const prices = vehicles.map((vehicle) =>
    services.find((service) => service.id === vehicle.service_id)
      ?.prices.find((price) => price.vehicle_type === vehicle.vehicle_type)?.price_minor,
  );
  const total = prices.reduce<number>((sum, price) => sum + (price ?? 0), 0);
  const selectedSlot = replacement || availability.data?.slots.some((slot) => slot.time === start && slot.available);
  const policyUrl = catalogue.data?.public_web_url?.replace(/\/$/, "");

  function updateVehicle(index: number, fields: Partial<VehicleInput>) {
    setVehicles((items) => items.map((item, i) => i === index ? { ...item, ...fields } : item));
    if ("service_id" in fields && !replacement) setStart("");
  }

  function prepareReview() {
    const coordinates = [latitude.trim(), longitude.trim()];
    if (!name.trim() || !phone.trim() || address.trim().length < 5) {
      setError("Enter the customer name, phone number and written service address.");
    } else if (!start || !selectedSlot || prices.some((price) => price === undefined)) {
      setError("Select a service and vehicle type for each car and an available appointment time.");
    } else if (!delivery || (delivery === "email" && (!email.trim() || !policyUrl))) {
      setError("Record how the customer will receive the policies.");
    } else if (replacement && (!replacement.version || reason.trim().length < 3)) {
      setError("Enter a reason for displacing the appointment.");
    } else if (showGps && coordinates.some(Boolean) && (
      !coordinates.every(Boolean) || coordinates.some((coordinate) => !Number.isFinite(Number(coordinate)))
      || Math.abs(Number(coordinates[0])) > 90 || Math.abs(Number(coordinates[1])) > 180
    )) {
      setError("Enter a valid latitude and longitude, or leave both blank.");
    } else {
      setError("");
      setReview(true);
    }
  }

  async function submit() {
    if (!catalogue.data || !delivery || submitting.current) return;
    if (!attempt.current) {
      attempt.current = {
        key: newClientEventId(),
        body: JSON.stringify({
          date: day, time: start,
          contact: { first_name: name, phone, email: email.trim() || null },
          location: {
            written_address: address, instructions: notes.trim() || null,
            latitude: showGps && latitude.trim() ? Number(latitude) : null,
            longitude: showGps && longitude.trim() ? Number(longitude) : null,
          },
          vehicles,
          expected_amount_minor: total,
          policy_revision: catalogue.data.policy_revision,
          policy_delivery: delivery,
          language,
          replacement: replacement ? {
            job_id: replacement.job_id, expected_version: replacement.version,
            reason, confirmed: true,
          } : null,
        }),
      };
    }
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await api<BookingReceipt>(path, {
        method: "POST",
        headers: { "Idempotency-Key": attempt.current.key },
        body: attempt.current.body,
      });
      setReceipt(result);
      setUncertain(false);
      onBooked(result.job_id, day);
    } catch (cause) {
      const uncertainResult = isUncertainMutationFailure(cause);
      setUncertain(uncertainResult);
      if (!uncertainResult) {
        attempt.current = null;
        setReview(false);
        if (!replacement) void availability.refetch();
        void catalogue.refetch();
      }
      setError(uncertainResult
        ? "The result is unknown. Retry this request to recover the same appointment."
        : domainErrorMessage(cause, "The appointment could not be booked."));
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  function confirm() {
    if (!replacement || uncertain) {
      void submit();
      return;
    }
    Alert.alert(
      "Replace this appointment?",
      "The original customer will need a new time. Their booking and payment records will be kept.",
      [
        { text: "Go back", style: "cancel" },
        { text: "Replace appointment", style: "destructive", onPress: () => void submit() },
      ],
    );
  }

  return (
    <Modal visible transparent animationType="slide" onRequestClose={() => {
      if (!busy && !uncertain) onClose();
    }}>
      <View style={styles.backdrop}>
        <ScrollView keyboardShouldPersistTaps="handled" style={styles.sheet} contentContainerStyle={styles.content}>
          <Text accessibilityRole="header" style={styles.title}>
            {replacement ? "Replace existing appointment" : "Book a Wash"}
          </Text>
          {receipt ? (
            <>
              <Text style={uiStyles.success}>
                Appointment booked · {receipt.reference} · {formatUaeDateTime(receipt.scheduled_start)}
              </Text>
              {receipt.replaced_appointment && <Text style={uiStyles.body}>The original appointment is in the manager follow-up queue.</Text>}
            </>
          ) : review ? (
            <>
              <Text accessibilityRole="header" style={uiStyles.label}>Review appointment</Text>
              <Text style={uiStyles.body}>{day} · {formatWallClockTime(start)} Abu Dhabi time</Text>
              <Text style={uiStyles.body}>{name} · {phone}</Text>
              <Text style={uiStyles.body}>{address}</Text>
              {vehicles.map((vehicle, i) => (
                <Text key={i} style={uiStyles.body}>
                  {services.find((service) => service.id === vehicle.service_id)?.name} · {vehicle.vehicle_type.replaceAll("_", " ")}
                </Text>
              ))}
              <Text style={uiStyles.label}>{catalogue.data?.settings.currency_code} {(total / 100).toFixed(2)} · Pay after service</Text>
              {replacement && <Text style={uiStyles.error}>This will displace the {formatUaeDateTime(replacement.scheduled_start)} appointment for {replacement.team_short_name ?? "the assigned team"}. Reason · {reason}</Text>}
              <AppButton title={uncertain ? "Retry safely" : replacement ? "Continue to replacement confirmation" : "Confirm booking"} loading={busy} disabled={busy} onPress={confirm} />
              {!uncertain && <AppButton title="Edit details" tone="secondary" disabled={busy} onPress={() => setReview(false)} />}
            </>
          ) : (
            <>
              {replacement ? (
                <Text style={uiStyles.body}>Occupied · {formatUaeDateTime(replacement.scheduled_start)} · {replacement.team_short_name ?? "Assigned team"}</Text>
              ) : (
                <DatePickerField label="Appointment date" value={day} minimumDate={wallDate(uaeDateKey())} onChange={(date) => { setDay(date); setStart(""); }} />
              )}
              {catalogue.isPending && <Text style={uiStyles.muted}>Loading services…</Text>}
              {catalogue.isError && <AppButton title="Retry loading services" tone="secondary" onPress={() => void catalogue.refetch()} />}
              {vehicles.map((vehicle, index) => {
                const service = services.find((item) => item.id === vehicle.service_id);
                return (
                  <Card key={index} style={styles.vehicle}>
                    <Text accessibilityRole="header" style={uiStyles.label}>Vehicle {index + 1}</Text>
                    <Text style={uiStyles.muted}>Service</Text>
                    <View style={styles.choices}>
                      {services.map((item) => (
                        <AppButton key={item.id} title={item.name}
                          tone={vehicle.service_id === item.id ? "primary" : "secondary"}
                          onPress={() => updateVehicle(index, { service_id: item.id, vehicle_type: "" })} />
                      ))}
                    </View>
                    {service && <Text style={uiStyles.muted}>Vehicle type</Text>}
                    <View style={styles.choices}>
                      {service?.prices.map((price) => (
                        <AppButton key={price.vehicle_type} title={price.vehicle_type.replaceAll("_", " ")}
                          tone={vehicle.vehicle_type === price.vehicle_type ? "primary" : "secondary"}
                          onPress={() => updateVehicle(index, { vehicle_type: price.vehicle_type })} />
                      ))}
                    </View>
                    <Entry label="Make (optional)" value={vehicle.make} onChange={(make) => updateVehicle(index, { make })} />
                    <Entry label="Model (optional)" value={vehicle.model} onChange={(model) => updateVehicle(index, { model })} />
                    <Entry label="Plate (optional)" value={vehicle.plate_number} onChange={(plate_number) => updateVehicle(index, { plate_number })} />
                    {vehicles.length > 1 && <AppButton title="Remove vehicle" tone="secondary" onPress={() => { setVehicles((items) => items.filter((_, i) => i !== index)); if (!replacement) setStart(""); }} />}
                  </Card>
                );
              })}
              {vehicles.length < 20 && <AppButton title="Add another vehicle" tone="secondary" onPress={() => { setVehicles((items) => [...items, newVehicle()]); if (!replacement) setStart(""); }} />}
              {!replacement && (
                <>
                  <Text style={uiStyles.label}>Available times · Abu Dhabi</Text>
                  {availability.isFetching && <Text style={uiStyles.muted}>Checking team capacity…</Text>}
                  {availability.isError && <AppButton title="Retry checking times" tone="secondary" onPress={() => void availability.refetch()} />}
                  {availability.data && !availability.data.slots.some((slot) => slot.available) && (
                    <Text style={uiStyles.muted}>No capacity for this selection. Choose another date or select an eligible appointment to replace in the calendar agenda.</Text>
                  )}
                  <View style={styles.choices}>
                    {availability.data?.slots.filter((slot) => slot.available).map((slot) => (
                      <AppButton key={slot.time} title={formatWallClockTime(slot.time)}
                        tone={start === slot.time ? "primary" : "secondary"} onPress={() => setStart(slot.time)} />
                    ))}
                  </View>
                </>
              )}
              <Entry label="Customer name" value={name} onChange={setName} />
              <Entry label="Customer phone" value={phone} onChange={setPhone} keyboardType="phone-pad" />
              <Entry label="Customer email (optional)" value={email} onChange={setEmail} keyboardType="email-address" />
              <Entry label="Written service address" value={address} onChange={setAddress} multiline />
              <Entry label="Service notes (optional)" value={notes} onChange={setNotes} multiline />
              <AppButton title={showGps ? "Remove coordinates" : "Add authorised coordinates (optional)"} tone="secondary" onPress={() => setShowGps(!showGps)} />
              {showGps && (
                <>
                  <Entry label="Latitude" value={latitude} onChange={setLatitude} keyboardType="numbers-and-punctuation" />
                  <Entry label="Longitude" value={longitude} onChange={setLongitude} keyboardType="numbers-and-punctuation" />
                </>
              )}
              {replacement && <Entry label="Reason for replacement" value={reason} onChange={setReason} multiline />}
              <Text style={uiStyles.label}>Provide the booking policies</Text>
              {policyUrl && Object.entries(policyLinks).map(([slug, title]) => (
                <AppButton key={slug} title={title} tone="secondary" onPress={() => void Linking.openURL(`${policyUrl}/${slug}`).catch(() => setError("Could not open the policy link."))} />
              ))}
              <AppButton title={language === "en" ? "Policy language · English" : "Policy language · Arabic"} tone="secondary" onPress={() => setLanguage(language === "en" ? "ar" : "en")} />
              <AppButton title="I provided the policies to the customer" tone={delivery === "provided" ? "primary" : "secondary"} onPress={() => setDelivery("provided")} />
              <AppButton title="Email links with the confirmation" disabled={!email.trim() || !policyUrl} tone={delivery === "email" ? "primary" : "secondary"} onPress={() => setDelivery("email")} />
              <AppButton title="Review appointment" disabled={!catalogue.data} onPress={prepareReview} />
            </>
          )}
          {error && <Text accessibilityRole="alert" style={uiStyles.error}>{error}</Text>}
          {!uncertain && <AppButton title={receipt ? "Done" : "Close"} tone="secondary" disabled={busy} onPress={onClose} />}
        </ScrollView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "flex-end" },
  sheet: { backgroundColor: colors.surface, maxHeight: "90%", ...webSheetStyle },
  content: { padding: spacing.lg, gap: spacing.md },
  title: { color: colors.text, fontSize: 24, fontWeight: "900" },
  vehicle: { gap: spacing.sm },
  choices: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
});

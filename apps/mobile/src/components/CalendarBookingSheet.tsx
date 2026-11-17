import { getStaffLanguage, staffMoney, t } from "../i18n";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Linking, Modal, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { operationalScope } from "../cache/policy";
import { domainErrorMessage } from "../errors/domainErrors";
import { isUncertainMutationFailure, newClientEventId } from "../idempotency/clientEventId";
import { api, type CalendarJob, type StaffContext } from "../lib";
import { colors, spacing } from "../theme";
import { formatUaeDateTime, formatWallClockTime, UAE_TIME_ZONE, uaeDateKey, wallDate } from "../time/uaeTime";
import { DatePickerField } from "./pickers";
import { AppButton, Card, Disclosure, uiStyles } from "./ui";
import { webSheetStyle } from "./webSheetStyle";
import { ConfirmationModal } from "./ConfirmationModal";

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
  capacity_exception: boolean;
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
  context, initialDate, overlap, onClose, onBooked,
}: {
  context: StaffContext;
  initialDate: string;
  overlap: CalendarJob | null;
  onClose: () => void;
  onBooked: (jobId: string, date: string) => void;
}) {
  const [day, setDay] = useState(overlap?.local_date ?? initialDate);
  const client = useQueryClient();
  const scroll = useRef<ScrollView>(null);
  const [start, setStart] = useState(() => overlap
    ? new Intl.DateTimeFormat("en-GB", {
        timeZone: UAE_TIME_ZONE, hourCycle: "h23", hour: "2-digit", minute: "2-digit", second: "2-digit",
      }).format(new Date(overlap.scheduled_start))
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
  const [delivery, setDelivery] = useState<"provided" | "email" | null>(null);
  const [language, setLanguage] = useState<"en" | "ar">("en");
  const [review, setReview] = useState(false);
  const [confirmOverlap, setConfirmOverlap] = useState(false);
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
    queryKey: ["calendar-booking-availability", scope, day, serviceIds, vehicles.map((vehicle) => vehicle.vehicle_type)],
    queryFn: ({ signal }) => {
      const query = new URLSearchParams({ date: day });
      serviceIds.forEach((id) => query.append("service_id", id));
      return api<Availability>(`${path}/availability?${query}`, { signal });
    },
    enabled: !overlap && serviceIds.every(Boolean),
    staleTime: 0,
    refetchOnMount: "always",
    refetchInterval: 15_000,
  });
  const prices = vehicles.map((vehicle) =>
    services.find((service) => service.id === vehicle.service_id)
      ?.prices.find((price) => price.vehicle_type === vehicle.vehicle_type)?.price_minor,
  );
  const total = prices.reduce<number>((sum, price) => sum + (price ?? 0), 0);
  const selectedSlot = overlap || availability.data?.slots.some((slot) => slot.time === start && slot.available);
  const policyUrl = catalogue.data?.public_web_url?.replace(/\/$/, "");

  function updateVehicle(index: number, fields: Partial<VehicleInput>) {
    setVehicles((items) => items.map((item, i) => i === index ? { ...item, ...fields } : item));
    if (("service_id" in fields || "vehicle_type" in fields) && !overlap) setStart("");
  }

  function prepareReview() {
    const coordinates = [latitude.trim(), longitude.trim()];
    if (overlap && !overlap.version) {
      setError(t("The selected appointment is no longer available. Refresh the calendar."));
    } else if (!name.trim() || !phone.trim() || address.trim().length < 5) {
      setError(t("Enter the customer name, phone number and written service address."));
    } else if (!start || !selectedSlot || prices.some((price) => price === undefined)) {
      setError(t("Select a service and vehicle type for each car and an available appointment time."));
    } else if (!delivery || (delivery === "email" && (!email.trim() || !policyUrl))) {
      setError(t("Record how the customer will receive the policies."));
    } else if (overlap && (!overlap.team_id || !/^([01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$/.test(start))) {
      setError(t("Enter a valid Abu Dhabi time in 24-hour format (HH:MM)."));
    } else if (showGps && coordinates.some(Boolean) && (
      !coordinates.every(Boolean) || coordinates.some((coordinate) => !Number.isFinite(Number(coordinate)))
      || Math.abs(Number(coordinates[0])) > 90 || Math.abs(Number(coordinates[1])) > 180
    )) {
      setError(t("Enter a valid latitude and longitude, or leave both blank."));
    } else {
      setError("");
      setReview(true);
      scroll.current?.scrollTo({ y: 0, animated: false });
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
          overlap: overlap ? {
            job_id: overlap.job_id, expected_version: overlap.version,
            team_id: overlap.team_id, confirmed: true,
          } : null,
        }),
      };
    }
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await api<BookingReceipt>(overlap ? `${path}/${overlap.job_id}/double-book` : path, {
        method: "POST",
        headers: { "Idempotency-Key": attempt.current.key },
        body: attempt.current.body,
      });
      setReceipt(result);
      setConfirmOverlap(false);
      setUncertain(false);
      for (const key of ["calendar", "jobs", "dashboard", "calendar-booking-availability"]) {
        void client.invalidateQueries({ queryKey: [key, scope] });
      }
      scroll.current?.scrollTo({ y: 0, animated: false });
      onBooked(result.job_id, day);
    } catch (cause) {
      const uncertainResult = isUncertainMutationFailure(cause);
      setUncertain(uncertainResult);
      if (!uncertainResult) {
        attempt.current = null;
        setReview(false);
        if (!overlap) { setStart(""); void availability.refetch(); }
        void catalogue.refetch();
      }
      setConfirmOverlap(false);
      setError(uncertainResult
        ? t("The result is unknown. Retry this request to recover the same appointment.")
        : domainErrorMessage(cause, "The appointment could not be booked."));
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  function confirm() {
    if (!overlap || uncertain) {
      void submit();
      return;
    }
    setConfirmOverlap(true);
  }

  return (
    <Modal visible transparent animationType="slide" onRequestClose={() => {
      if (!busy && !uncertain) onClose();
    }}>
      <View style={[styles.backdrop, { direction: getStaffLanguage() === "ar" ? "rtl" : "ltr" }]}>
        <ScrollView ref={scroll} keyboardShouldPersistTaps="handled" style={styles.sheet} contentContainerStyle={styles.content}>
          <View style={uiStyles.row}>
            <Text accessibilityRole="header" style={styles.title}>
              {overlap ? t("Double-book a wash") : t("Book a Wash")}
            </Text>
            {!receipt && !uncertain ? <AppButton title={t("Close")} tone="secondary" disabled={busy} onPress={onClose} /> : null}
          </View>
          {receipt ? (
            <>
              <Text style={uiStyles.success}>
                {" " + t("Appointment booked ·") + " "}{receipt.reference} · {formatUaeDateTime(receipt.scheduled_start)}
              </Text>
              {receipt.capacity_exception && <Text style={uiStyles.body}>{t("Both appointments remain independently confirmed.")}</Text>}
            </>
          ) : review ? (
            <>
              <Text accessibilityRole="header" style={uiStyles.label}>{t("Review appointment")}</Text>
              <Text style={uiStyles.body}>{day} · {formatWallClockTime(start)} {" " + t("Abu Dhabi time") + ""}</Text>
              <Text style={uiStyles.body}>{name} · {phone}</Text>
              <Text style={uiStyles.body}>{address}</Text>
              {vehicles.map((vehicle, i) => (
                <Text key={i} style={uiStyles.body}>
                  {services.find((service) => service.id === vehicle.service_id)?.name} · {t(vehicle.vehicle_type.replaceAll("_", " "))}
                </Text>
              ))}
              <Text style={uiStyles.label}>{staffMoney(total, catalogue.data?.settings.currency_code)} {" " + t("· Pay after service") + ""}</Text>
              {overlap && <Text style={uiStyles.error}>{"" + t("This adds an overlapping appointment for") + " "}{overlap.team_short_name ?? t("the assigned team")}{t(". Both bookings stay confirmed.")}</Text>}
              <AppButton title={uncertain ? t("Retry safely") : overlap ? t("Double-book this time") : t("Confirm booking")} loading={busy} disabled={busy} onPress={confirm} />
              {!uncertain && <AppButton title={t("Edit details")} tone="secondary" disabled={busy} onPress={() => setReview(false)} />}
            </>
          ) : (
            <>
              {overlap ? (
                <>
                  <Text style={uiStyles.body}>{"" + t("Occupied ·") + " "}{formatUaeDateTime(overlap.scheduled_start)} · {overlap.team_short_name ?? t("Assigned team")}</Text>
                  <Entry label={t("New appointment time (HH:MM)")} value={start} onChange={setStart} />
                </>
              ) : (
              <>
                <Text style={uiStyles.muted}>{t("Choose a service and time, then enter the customer's details. Payment is collected after service.")}</Text>
                <DatePickerField label={t("Appointment date")} value={day} minimumDate={wallDate(uaeDateKey())} onChange={(date) => { setDay(date); setStart(""); }} />
              </>
              )}
              {catalogue.isPending && <Text style={uiStyles.muted}>{t("Loading services…")}</Text>}
              {catalogue.isError && <AppButton title={t("Retry loading services")} tone="secondary" onPress={() => void catalogue.refetch()} />}
              {vehicles.map((vehicle, index) => {
                const service = services.find((item) => item.id === vehicle.service_id);
                return (
                  <Card key={index} style={styles.vehicle}>
                    <Text accessibilityRole="header" style={uiStyles.label}>{"" + t("Vehicle") + " "}{index + 1}</Text>
                    <Text style={uiStyles.muted}>{t("Service")}</Text>
                    <View style={styles.choices}>
                      {services.map((item) => (
                        <AppButton key={item.id} title={item.name}
                          tone={vehicle.service_id === item.id ? "primary" : "secondary"}
                          onPress={() => updateVehicle(index, { service_id: item.id, vehicle_type: "" })} />
                      ))}
                    </View>
                    {service && <Text style={uiStyles.muted}>{t("Vehicle type")}</Text>}
                    <View style={styles.choices}>
                      {service?.prices.map((price) => (
                        <AppButton key={price.vehicle_type} title={t(price.vehicle_type.replaceAll("_", " "))}
                          tone={vehicle.vehicle_type === price.vehicle_type ? "primary" : "secondary"}
                          onPress={() => updateVehicle(index, { vehicle_type: price.vehicle_type })} />
                      ))}
                    </View>
                    <Disclosure title={t("Vehicle details (optional)")}>
                      <Entry label={t("Make (optional)")} value={vehicle.make} onChange={(make) => updateVehicle(index, { make })} />
                      <Entry label={t("Model (optional)")} value={vehicle.model} onChange={(model) => updateVehicle(index, { model })} />
                      <Entry label={t("Plate (optional)")} value={vehicle.plate_number} onChange={(plate_number) => updateVehicle(index, { plate_number })} />
                    </Disclosure>
                    {vehicles.length > 1 && <AppButton title={t("Remove vehicle")} tone="secondary" onPress={() => { setVehicles((items) => items.filter((_, i) => i !== index)); if (!overlap) setStart(""); }} />}
                  </Card>
                );
              })}
              {vehicles.length < 20 && <AppButton title={t("Add another vehicle")} tone="secondary" onPress={() => { setVehicles((items) => [...items, newVehicle()]); if (!overlap) setStart(""); }} />}
              {!overlap && (
                <>
                  <Text style={uiStyles.label}>{t("Available times · Abu Dhabi")}</Text>
                  {!serviceIds.every(Boolean) ? <Text style={uiStyles.muted}>{t("Select a service above to see available times.")}</Text> : null}
                  {availability.isFetching && <Text style={uiStyles.muted}>{t("Checking team capacity…")}</Text>}
                  {availability.isError && <AppButton title={t("Retry checking times")} tone="secondary" onPress={() => void availability.refetch()} />}
                  {availability.data && !availability.data.slots.some((slot) => slot.available) && (
                    <Text style={uiStyles.muted}>{t("No available times for this date")}</Text>
                  )}
                  <View style={styles.choices}>
                    {availability.data?.slots.filter((slot) => slot.available).map((slot) => (
                      <AppButton key={slot.time} title={formatWallClockTime(slot.time)}
                        tone={start === slot.time ? "primary" : "secondary"} onPress={() => setStart(slot.time)} />
                    ))}
                  </View>
                </>
              )}
              <Entry label={t("Customer name")} value={name} onChange={setName} />
              <Entry label={t("Customer phone")} value={phone} onChange={setPhone} keyboardType="phone-pad" />
              <Entry label={t("Customer email (optional)")} value={email} onChange={setEmail} keyboardType="email-address" />
              <Entry label={t("Written service address")} value={address} onChange={setAddress} multiline />
              <Disclosure title={t("Service notes & coordinates (optional)")}>
              <Entry label={t("Service notes (optional)")} value={notes} onChange={setNotes} multiline />
              <AppButton title={showGps ? t("Remove coordinates") : t("Add authorised coordinates (optional)")} tone="secondary" onPress={() => setShowGps(!showGps)} />
              {showGps && (
                <>
                  <Entry label={t("Latitude")} value={latitude} onChange={setLatitude} keyboardType="numbers-and-punctuation" />
                  <Entry label={t("Longitude")} value={longitude} onChange={setLongitude} keyboardType="numbers-and-punctuation" />
                </>
              )}
              </Disclosure>
              <Text style={uiStyles.label}>{t("Provide the booking policies")}</Text>
              <Text style={uiStyles.muted}>{t("Choose how the customer receives the policies before confirming.")}</Text>
              <Disclosure title={t("Read booking policies")}>
              {policyUrl && Object.entries(policyLinks).map(([slug, title]) => (
                <AppButton key={slug} title={title} tone="secondary" onPress={() => void Linking.openURL(`${policyUrl}/${slug}`).catch(() => setError(t("Could not open the policy link.")))} />
              ))}
              </Disclosure>
              <AppButton title={language === "en" ? t("Policy language · English") : t("Policy language · Arabic")} tone="secondary" onPress={() => setLanguage(language === "en" ? "ar" : "en")} />
              <AppButton title={t("I provided the policies to the customer")} tone={delivery === "provided" ? "primary" : "secondary"} onPress={() => setDelivery("provided")} />
              <AppButton title={t("Email links with the confirmation")} disabled={!email.trim() || !policyUrl} tone={delivery === "email" ? "primary" : "secondary"} onPress={() => setDelivery("email")} />
              <AppButton title={t("Review appointment")} disabled={!catalogue.data} onPress={prepareReview} />
            </>
          )}
          {error ? <Text accessibilityRole="alert" style={uiStyles.error}>{t(error)}</Text> : null}
          {receipt ? <AppButton title={t("Done")} tone="secondary" onPress={onClose} /> : null}
        </ScrollView>
        {confirmOverlap && <ConfirmationModal visible title={t("Double-book this time?")}
          description={t("This creates another appointment for an occupied time. Both appointments will remain independently confirmed.")}
          backLabel={t("Go back")} confirmLabel={t("Confirm double-booking")} busy={busy}
          onBack={() => setConfirmOverlap(false)} onConfirm={() => void submit()}>
          <View style={styles.confirmDetails}>
            <Text style={styles.confirmTeam}>{overlap?.team_short_name ?? t("Assigned team")}</Text>
            <Text style={uiStyles.body}>{day} · {formatWallClockTime(start)}</Text>
            <Text style={uiStyles.muted}>{t("Abu Dhabi time")}</Text>
          </View>
        </ConfirmationModal>}
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "flex-end" },
  sheet: { backgroundColor: colors.surface, maxHeight: "90%", ...webSheetStyle },
  content: { padding: spacing.lg, gap: spacing.md },
  title: { color: colors.text, fontSize: 24, fontWeight: "700", flex: 1 },
  vehicle: { gap: spacing.sm },
  choices: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  confirmDetails: { padding: spacing.lg, gap: spacing.sm, borderRadius: 12, backgroundColor: colors.surfaceElevated },
  confirmTeam: { color: colors.text, fontSize: 18, fontWeight: "600" },
});

import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Linking, Text } from "react-native";
import { domainErrorMessage } from "../errors/domainErrors";
import { ClientEventIdStore } from "../idempotency/clientEventId";
import { api, type Job, type StaffContext } from "../lib";
import { AppButton, Card, uiStyles } from "./ui";

const channels = {
  phone: "Record policies provided by phone",
  whatsapp: "Record policy links sent via WhatsApp",
  in_person: "Record policies provided in person",
  email: "Email policy links",
};
const links = {
  "terms-and-conditions": "Terms & Conditions",
  "cancellation-and-refund-policy": "Cancellation & Refund Policy",
  "privacy-policy": "Privacy Policy",
};

export function BookingPolicyProvision({ context, job }: { context: StaffContext; job: Job }) {
  const [open, setOpen] = useState(false);
  const [language, setLanguage] = useState<"en" | "ar">("en");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const keys = useRef(new ClientEventIdStore()).current;
  const policies = useQuery({
    queryKey: ["customer-policy-revision", context.business_id, context.staff_id],
    queryFn: () => api<{ revision: string; public_web_url: string | null }>("/api/v1/staff/customer-policies"),
    enabled: open,
    refetchOnMount: "always",
  });

  async function record(channel: keyof typeof channels) {
    if (!policies.data || busy) return;
    const { revision } = policies.data;
    const operation = `${job.booking_id}:${channel}:${language}:${revision}`;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const result = await api<{ email_queued: boolean }>(`/api/v1/staff/bookings/${job.booking_id}/policy-provision`, {
        method: "POST",
        headers: { "Idempotency-Key": keys.get(operation) },
        body: JSON.stringify({ channel, language, revision }),
      });
      keys.succeeded(operation);
      setSuccess(result.email_queued ? "Policy email queued." : "Policy provision recorded.");
    } catch (reason) {
      keys.failed(operation, reason);
      setError(domainErrorMessage(reason, "Could not record policy provision."));
      void policies.refetch();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <AppButton title={open ? "Hide booking policies" : "Booking policies"} tone="secondary" disabled={busy} onPress={() => setOpen(!open)} />
      {open && (
        <>
          <Text style={uiStyles.muted}>For an assisted booking, record how you provided the policies or send the links to the booking email.</Text>
          {policies.isPending && <Text style={uiStyles.muted}>Loading policies…</Text>}
          {policies.isError && <AppButton title="Retry loading policies" tone="secondary" onPress={() => void policies.refetch()} />}
          {policies.data?.public_web_url && Object.entries(links).map(([path, label]) => (
            <AppButton key={path} title={label} tone="secondary" onPress={() => {
              const base = policies.data?.public_web_url?.replace(/\/$/, "");
              if (base) void Linking.openURL(`${base}/${path}`).catch(() => setError("Could not open the policy."));
            }} />
          ))}
          <AppButton title={language === "en" ? "Language: English" : "Language: Arabic"} tone="secondary" disabled={busy} onPress={() => setLanguage(language === "en" ? "ar" : "en")} />
          {Object.entries(channels).map(([channel, label]) => (
            <AppButton key={channel} title={label} tone="secondary" disabled={busy || !policies.data || (channel === "email" && (!job.customer_email || !policies.data.public_web_url))} onPress={() => void record(channel as keyof typeof channels)} />
          ))}
          {success && <Text style={uiStyles.success}>{success}</Text>}
          {error && <Text style={uiStyles.error}>{error}</Text>}
        </>
      )}
    </Card>
  );
}

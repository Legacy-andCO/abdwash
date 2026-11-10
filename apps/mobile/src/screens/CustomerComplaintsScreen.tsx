import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Linking, RefreshControl, ScrollView, Text, TextInput, View } from "react-native";
import { capabilities } from "../capabilities";
import { AppButton, Card, EmptyState, ScreenTitle, Skeleton, uiStyles } from "../components/ui";
import { domainErrorMessage } from "../errors/domainErrors";
import { api, type StaffContext } from "../lib";
import { spacing } from "../theme";
import { formatUaeDateTime } from "../time/uaeTime";

const route = "/api/v1/staff/complaints";
const pageSize = 30;
const categories: Record<string, string> = {
  service: "Service quality", damage: "Vehicle damage", belongings: "Missing belongings",
  booking: "Booking", payment: "Payment or refund", conduct: "Staff conduct",
  privacy: "Privacy", other: "Other",
};

type ComplaintSummary = { reference: string; category: string; created_at: string };
type ComplaintDetail = ComplaintSummary & {
  name: string;
  email: string | null;
  phone: string | null;
  booking_reference: string | null;
  service_date: string | null;
  description: string;
  language: string;
  attachment_count: number;
  notification_status: string | null;
};

export function CustomerComplaintsScreen({
  context, onBack,
}: {
  context: StaffContext;
  onBack: () => void;
}) {
  const [offset, setOffset] = useState(0);
  const [reference, setReference] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const allowed = capabilities(context.role).canManageCustomers;
  const scope = ["customer-complaints", context.business_id, context.staff_id, context.role];
  const list = useQuery({
    queryKey: [...scope, "list", offset],
    queryFn: ({ signal }) => api<ComplaintSummary[]>(`${route}?limit=${pageSize}&offset=${offset}`, { signal }),
    enabled: allowed && !selected,
    gcTime: 0,
  });
  const detail = useQuery({
    queryKey: [...scope, "detail", selected],
    queryFn: ({ signal }) => api<ComplaintDetail>(`${route}/${selected}`, { signal }),
    enabled: allowed && Boolean(selected),
    gcTime: 0,
  });
  const [openingEvidence, setOpeningEvidence] = useState(false);
  const [evidenceError, setEvidenceError] = useState("");

  async function openEvidence(index: number) {
    setOpeningEvidence(true);
    setEvidenceError("");
    try {
      const { url } = await api<{ url: string }>(`${route}/${selected}/evidence/${index}/download`, {
        method: "POST",
      });
      await Linking.openURL(url);
    } catch (reason) {
      setEvidenceError(domainErrorMessage(reason, "Could not open the photo."));
    } finally {
      setOpeningEvidence(false);
    }
  }

  if (!allowed) return <EmptyState title="Complaints unavailable" body="Manager access is required." />;
  const query = selected ? detail : list;
  const normalized = reference.trim().toUpperCase();
  return (
    <ScrollView
      contentContainerStyle={uiStyles.content}
      refreshControl={<RefreshControl refreshing={query.isRefetching} onRefresh={() => void query.refetch()} />}
    >
      <AppButton title={selected ? "Back to complaints" : "Back to Today"} tone="secondary" onPress={() => {
        if (selected) {
          setEvidenceError("");
          setSelected(null);
        } else onBack();
      }} />
      <ScreenTitle title={selected ? "Complaint details" : "Customer complaints"} />
      {!selected && (
        <>
          <TextInput
            accessibilityLabel="Complaint reference"
            autoCapitalize="characters"
            autoCorrect={false}
            placeholder="Complaint reference"
            style={uiStyles.field}
            value={reference}
            onChangeText={setReference}
            maxLength={35}
          />
          <AppButton title="Find by reference" tone="secondary" disabled={!/^TC-[0-9A-F]{32}$/.test(normalized)} onPress={() => setSelected(normalized)} />
        </>
      )}
      {query.isPending && <Skeleton rows={3} />}
      {query.isError && (
        <Text style={uiStyles.error}>{domainErrorMessage(query.error, "Could not load complaints. Pull down to retry.")}</Text>
      )}
      {selected && detail.data && (
        <Card>
          <Text selectable style={uiStyles.label}>{detail.data.reference}</Text>
          <Text style={uiStyles.muted}>{formatUaeDateTime(detail.data.created_at)} · {categories[detail.data.category]}</Text>
          <Text style={uiStyles.body}>{detail.data.name}</Text>
          {detail.data.email && <Text selectable style={uiStyles.body}>{detail.data.email}</Text>}
          {detail.data.phone && <Text selectable style={uiStyles.body}>{detail.data.phone}</Text>}
          {detail.data.booking_reference && <Text selectable style={uiStyles.body}>Booking {detail.data.booking_reference}</Text>}
          {detail.data.service_date && <Text style={uiStyles.body}>Service date {detail.data.service_date}</Text>}
          <Text selectable style={[uiStyles.body, { writingDirection: detail.data.language === "ar" ? "rtl" : "ltr" }]}>
            {detail.data.description}
          </Text>
          <Text style={uiStyles.muted}>Inbox notification · {detail.data.notification_status ?? "Unavailable"}</Text>
          {Array.from({ length: detail.data.attachment_count }, (_, index) => (
            <AppButton key={index} title={`Download photo ${index + 1}`} tone="secondary" disabled={openingEvidence} onPress={() => void openEvidence(index)} />
          ))}
          {evidenceError && <Text style={uiStyles.error}>{evidenceError}</Text>}
        </Card>
      )}
      {!selected && list.data?.map((row) => (
        <Card key={row.reference}>
          <Text style={uiStyles.label}>{categories[row.category]}</Text>
          <Text selectable style={uiStyles.body}>{row.reference}</Text>
          <Text style={uiStyles.muted}>{formatUaeDateTime(row.created_at)}</Text>
          <AppButton title="View complaint" tone="secondary" onPress={() => setSelected(row.reference)} />
        </Card>
      ))}
      {!selected && list.data && (
        <View style={{ gap: spacing.sm }}>
          {!list.data.length && <EmptyState title="No complaints on this page" body="New reports will appear here." />}
          {offset > 0 && <AppButton title="Previous page" tone="secondary" onPress={() => setOffset(offset - pageSize)} />}
          {list.data.length === pageSize && <AppButton title="Next page" tone="secondary" onPress={() => setOffset(offset + pageSize)} />}
        </View>
      )}
    </ScrollView>
  );
}

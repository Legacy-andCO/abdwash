import { useState } from "react";
import { Image, Text, TextInput, View } from "react-native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type StaffContext } from "../lib";
import { operationalScope } from "../cache/policy";
import { staffMoney, staffLocale, t } from "../i18n";
import { AppButton, Card, Skeleton, uiStyles } from "./ui";

type Balance = {
  job_id: string;
  reference: string;
  customer_first_name: string;
  customer_surname: string;
  currency_code: string;
  remaining_minor: number;
  pending_minor: number;
};
type Receipt = Omit<Balance, "remaining_minor" | "pending_minor"> & {
  id: string;
  amount_minor: number;
  transaction_type: string;
  status: string;
  display_name: string;
  provider_transaction_id: string | null;
  created_at: string;
  reviewed_at: string | null;
  reviewer: string | null;
  rejection_reason: string | null;
  has_screenshot: boolean;
};

export function PaymentReviewList({ context }: { context: StaffContext }) {
  const [mode, setMode] = useState<"outstanding" | "payment-history">(
    "outstanding",
  );
  const [page, setPage] = useState(0);
  const scope = operationalScope(context);
  const query = useQuery({
    queryKey: ["finance", scope, mode, page],
    queryFn: () =>
      api<(Balance | Receipt)[]>(
        `/api/v1/staff/finance/${mode}?offset=${page * 50}`,
      ),
  });
  return (
    <>
      {(["outstanding", "payment-history"] as const).map((key) => (
        <AppButton
          key={key}
          title={t(
            key === "outstanding" ? "Outstanding payments" : "Payment history",
          )}
          tone={mode === key ? "primary" : "secondary"}
          onPress={() => {
            setPage(0);
            setMode(key);
          }}
        />
      ))}
      {query.isPending ? (
        <Skeleton rows={2} />
      ) : query.isError ? (
        <AppButton
          title={t("Try again")}
          onPress={() => void query.refetch()}
        />
      ) : query.data?.length === 0 ? (
        <Text style={uiStyles.body}>{t("No payments to show")}</Text>
      ) : (
        query.data?.map((item) =>
          "status" in item ? (
            <ReceiptCard key={item.id} item={item} />
          ) : (
            <Card key={item.job_id}>
              <Text style={uiStyles.label}>
                {item.reference} · {item.customer_first_name}{" "}
                {item.customer_surname}
              </Text>
              <Text style={uiStyles.body}>
                {staffMoney(item.remaining_minor, item.currency_code)}
              </Text>
              {item.pending_minor > 0 && (
                <Text style={uiStyles.muted}>
                  {t("Pending verification")} ·{" "}
                  {staffMoney(item.pending_minor, item.currency_code)}
                </Text>
              )}
            </Card>
          ),
        )
      )}
      {page > 0 && (
        <AppButton title={t("Previous")} onPress={() => setPage(page - 1)} />
      )}
      {query.data?.length === 50 && (
        <AppButton title={t("Next")} onPress={() => setPage(page + 1)} />
      )}
    </>
  );
}
function ReceiptCard({ item }: { item: Receipt }) {
  const [reason, setReason] = useState("");
  const [show, setShow] = useState(false);
  const client = useQueryClient();
  const proof = useQuery({
    queryKey: ["payment-proof", item.id],
    queryFn: () =>
      api<{ jpeg: string }>(
        `/api/v1/staff/finance/payments/${item.id}/screenshot`,
      ),
    enabled: show,
    gcTime: 0,
    meta: { persist: false },
  });
  const review = useMutation({
    mutationFn: (decision: "confirm" | "reject") =>
      api<void>(
        `/api/v1/staff/jobs/${item.job_id}/payments/${item.id}/review`,
        {
          method: "POST",
          body: JSON.stringify({
            decision,
            reason: decision === "reject" ? reason : null,
          }),
        },
      ),
    onSettled: () => client.invalidateQueries(),
  });
  return (
    <Card>
      <Text style={uiStyles.label}>
        {item.reference} · {item.customer_first_name} {item.customer_surname}
      </Text>
      <Text style={uiStyles.body}>
        {staffMoney(item.amount_minor, item.currency_code)} ·{" "}
        {t(item.transaction_type === "cash_payment" ? "Cash" : "Card")}
      </Text>
      <Text style={uiStyles.muted}>
        {item.display_name} ·{" "}
        {new Date(item.created_at).toLocaleString(staffLocale())}
      </Text>
      <Text style={uiStyles.body}>
        {t(
          item.status === "pending"
            ? "Pending verification"
            : item.status === "succeeded"
              ? "Verified"
              : "Rejected",
        )}
      </Text>
      {item.reviewed_at && (
        <Text style={uiStyles.muted}>
          {item.reviewer} ·{" "}
          {new Date(item.reviewed_at).toLocaleString(staffLocale())}
        </Text>
      )}
      {item.provider_transaction_id && (
        <Text selectable style={uiStyles.body}>
          {t("Reference")} · {item.provider_transaction_id}
        </Text>
      )}
      {item.rejection_reason && (
        <Text style={uiStyles.body}>{item.rejection_reason}</Text>
      )}
      {item.has_screenshot && (
        <AppButton
          tone="secondary"
          title={t(show ? "Hide" : "View screenshot")}
          onPress={() => setShow(!show)}
        />
      )}
      {show &&
        (proof.data ? (
          <Image
            accessibilityLabel={t("View screenshot")}
            source={{ uri: "data:image/jpeg;base64," + proof.data.jpeg }}
            resizeMode="contain"
            style={{ width: "100%", height: 280 }}
          />
        ) : proof.isError ? (
          <AppButton
            title={t("Try again")}
            onPress={() => void proof.refetch()}
          />
        ) : (
          <Skeleton rows={1} />
        ))}
      {item.status === "pending" && (
        <View style={{ gap: 8 }}>
          <AppButton
            title={t("Confirm payment")}
            disabled={review.isPending}
            onPress={() => review.mutate("confirm")}
          />
          <TextInput
            style={uiStyles.field}
            accessibilityLabel={t("Rejection reason")}
            placeholder={t("Rejection reason")}
            value={reason}
            maxLength={500}
            onChangeText={setReason}
          />
          <AppButton
            tone="danger"
            title={t("Reject payment")}
            disabled={review.isPending || !reason.trim()}
            onPress={() => review.mutate("reject")}
          />
          {review.isError && (
            <Text accessibilityRole="alert" style={uiStyles.error}>
              {review.error.message}
            </Text>
          )}
        </View>
      )}
    </Card>
  );
}

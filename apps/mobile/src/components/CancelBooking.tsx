import { getStaffLanguage, t } from "../i18n";
import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Text, TextInput, View } from "react-native";
import { operationalScope, queryKeys } from "../cache/policy";
import { domainErrorMessage } from "../errors/domainErrors";
import { isUncertainMutationFailure, newClientEventId } from "../idempotency/clientEventId";
import { api, type Job, type StaffContext, type CalendarJob } from "../lib";
import { formatUaeDateTime } from "../time/uaeTime";
import { ConfirmationModal } from "./ConfirmationModal";
import { AppButton, uiStyles } from "./ui";

type Result = { booking_id: string; job_id: string; email_queued: boolean; manual_notification_required: boolean };

export function CancelBooking({ context, job }: { context: StaffContext; job: Job }) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [review, setReview] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const submitting = useRef(false);
  const attempt = useRef<{ key: string; body: string } | null>(null);
  const eligible = ["manager", "admin"].includes(context.role)
    && ["unassigned", "assigned", "en_route", "arrived", "rescheduling_required"].includes(job.status);
  async function cancel() {
    if (submitting.current || !eligible || !job.version) return;
    submitting.current = true; setBusy(true); setError("");
    attempt.current ??= { key: newClientEventId(), body: JSON.stringify({ reason: reason.trim(), expected_version: job.version, language: getStaffLanguage() }) };
    try {
      const result = await api<Result>(`/api/v1/staff/bookings/${job.booking_id}/cancel`, {
        method: "POST", body: attempt.current.body, headers: { "Idempotency-Key": attempt.current.key },
      });
      const scope = operationalScope(context);
      client.setQueryData<Job>(queryKeys.job(scope, job.id), current => ({ ...(current ?? job), status: "cancelled", version: Math.max(current?.version ?? 1, (job.version ?? 1) + 1) }));
      client.setQueriesData<{ jobs: CalendarJob[] }>({ queryKey: ["calendar", scope] }, current => current ? { ...current, jobs: current.jobs.map(item => item.job_id === job.id ? { ...item, status: "cancelled", can_double_book: false } : item) } : current);
      for (const key of ["jobs", "dashboard", "calendar", "reports", "communications", "cancellations", "calendar-booking-availability"]) void client.invalidateQueries({ queryKey: [key, scope] });
      setNotice(result.email_queued ? t("Booking cancelled. The customer email is queued.") : t("Booking cancelled. Notify the customer manually; no valid email address is available."));
      setOpen(false); setUncertain(false); attempt.current = null;
    } catch (cause) {
      const unknown = isUncertainMutationFailure(cause);
      setUncertain(unknown);
      if (!unknown) attempt.current = null;
      setError(unknown ? t("The result is unknown. Retry safely to recover the same cancellation.") : domainErrorMessage(cause, "The booking could not be cancelled."));
    } finally { submitting.current = false; setBusy(false); }
  }
  return <>
    {eligible ? <AppButton title={t("Cancel booking")} tone="danger" onPress={() => { setOpen(true); setReview(false); setError(""); }} /> : null}
    {notice ? <Text role="status" style={uiStyles.success}>{t(notice)}</Text> : null}
    <ConfirmationModal visible={open} title={review ? t("Confirm cancellation") : t("Cancel booking")}
      description={review ? t("This cancels the appointment and its pending reminders. Payment records are preserved. No refund will be issued automatically.") : t("Enter a reason, then review the cancellation before confirming.")}
      confirmLabel={uncertain ? t("Retry safely") : review ? t("Confirm cancellation") : t("Review cancellation")}
      backLabel={review ? t("Go back") : t("Keep booking")} confirmTone={review ? "danger" : "primary"}
      busy={busy} backDisabled={uncertain} disabled={reason.trim().length < 3 || !job.version}
      onBack={() => { if (uncertain) return; if (review) setReview(false); else setOpen(false); }}
      onConfirm={() => { if (review) void cancel(); else setReview(true); }}>
      <View style={{ gap: 8 }}>
        <Text style={uiStyles.body}>{job.booking_reference} · {job.assigned_team_name ?? t("Unassigned")}</Text>
        <Text style={uiStyles.body}>{formatUaeDateTime(job.scheduled_start)}</Text>
        {review ? <Text style={uiStyles.body}>{reason}</Text> : <>
          <Text style={uiStyles.label}>{t("Cancellation reason")}</Text>
          <TextInput accessibilityLabel={t("Cancellation reason")} style={uiStyles.field} value={reason} onChangeText={setReason} multiline maxLength={1000} />
        </>}
        {error ? <Text accessibilityRole="alert" style={uiStyles.error}>{t(error)}</Text> : null}
      </View>
    </ConfirmationModal>
  </>;
}

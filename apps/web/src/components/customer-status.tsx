import type { CustomerBookingStatus } from "@/lib/types";
import { useI18n } from "./i18n-provider";

export function CustomerStatus({ status, compact = false }: { status: CustomerBookingStatus; compact?: boolean }) {
  const { t } = useI18n();
  const stages = [t("status.confirmed"), t("status.teamAssigned"), t("status.driverEnRoute"), t("status.driverArrived"), t("status.inProgress"), t("status.completed")];
  const labels: Partial<Record<string, string>> = { confirmed: t("status.confirmed"), en_route: t("status.driverEnRoute"), arrived: t("status.driverArrived"), in_progress: t("status.inProgress"), completed: t("status.completed"), cancelled: t("status.cancelled"), cancellation_requested: t("status.cancellationRequested"), pending_payment: t("status.pending") };
  const terminal = ["cancelled", "cancellation_requested", "pending_payment"].includes(status.key);
  return <div className={compact ? "customer-status compact" : "customer-status"}>
    <span className={`status-pill status-${status.key}`}>{labels[status.key] ?? status.label}</span>
    {!compact && !terminal && <ol aria-label={t("booking.progress")}>
      {stages.map((label, index) => <li key={label} className={index <= status.stage ? "complete" : ""}><span aria-hidden="true">{index < status.stage ? "✓" : index + 1}</span>{label}</li>)}
    </ol>}
  </div>;
}

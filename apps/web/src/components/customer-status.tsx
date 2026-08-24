import type { CustomerBookingStatus } from "@/lib/types";

const stages = ["Confirmed", "Team assigned", "Driver on the way", "Wash in progress", "Completed"];

export function CustomerStatus({ status, compact = false }: { status: CustomerBookingStatus; compact?: boolean }) {
  const terminal = ["cancelled", "cancellation_requested", "pending_payment"].includes(status.key);
  return <div className={compact ? "customer-status compact" : "customer-status"}>
    <span className={`status-pill status-${status.key}`}>{status.label}</span>
    {!compact && !terminal && <ol aria-label="Booking progress">
      {stages.map((label, index) => <li key={label} className={index <= status.stage ? "complete" : ""}><span aria-hidden="true">{index < status.stage ? "✓" : index + 1}</span>{label}</li>)}
    </ol>}
  </div>;
}

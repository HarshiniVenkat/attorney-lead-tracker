import { cn } from "@/lib/utils";
import type { EmailDeliveryStatus, LeadState } from "@/lib/types";

const LEAD_STATE_STYLES: Record<LeadState, string> = {
  PENDING: "bg-amber-50 text-amber-800 ring-amber-200",
  REACHED_OUT: "bg-emerald-50 text-emerald-800 ring-emerald-200",
};

const LEAD_STATE_LABELS: Record<LeadState, string> = {
  PENDING: "Pending",
  REACHED_OUT: "Reached out",
};

export function StateBadge({ state }: { state: LeadState }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1",
        "text-xs font-medium ring-1 ring-inset",
        LEAD_STATE_STYLES[state],
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          state === "PENDING" ? "bg-amber-500" : "bg-emerald-500",
        )}
        aria-hidden="true"
      />
      {LEAD_STATE_LABELS[state]}
    </span>
  );
}

const DELIVERY_STYLES: Record<EmailDeliveryStatus, string> = {
  SENT: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  PENDING: "bg-slate-100 text-slate-600 ring-slate-200",
  FAILED: "bg-red-50 text-red-700 ring-red-200",
};

export function DeliveryBadge({ status }: { status: EmailDeliveryStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5",
        "text-xs font-medium ring-1 ring-inset",
        DELIVERY_STYLES[status],
      )}
    >
      {status.toLowerCase()}
    </span>
  );
}

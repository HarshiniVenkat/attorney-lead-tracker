import Link from "next/link";

import { MarkReachedOutButton } from "@/components/admin/mark-reached-out";
import { StateBadge } from "@/components/ui/badge";
import type { Lead } from "@/lib/types";
import { formatRelative, initialsOf } from "@/lib/utils";

export function LeadsTable({ leads }: { leads: Lead[] }) {
  if (leads.length === 0) {
    return <EmptyState />;
  }

  return (
    // Horizontal scroll is confined to the table so the page body never
    // scrolls sideways on narrow screens.
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-left">
        <thead>
          <tr className="border-b border-line bg-surface-muted">
            {["Name", "Email", "Status", "Submitted", ""].map((heading, index) => (
              <th
                key={heading || index}
                scope="col"
                className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-ink-subtle"
              >
                {heading}
              </th>
            ))}
          </tr>
        </thead>

        <tbody className="divide-y divide-line">
          {leads.map((lead) => (
            <tr key={lead.id} className="transition-colors hover:bg-surface-muted">
              <td className="px-4 py-3">
                <div className="flex items-center gap-3">
                  <span
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-sunken text-xs font-semibold text-ink-muted"
                    aria-hidden="true"
                  >
                    {initialsOf(lead.first_name, lead.last_name)}
                  </span>
                  <Link
                    href={`/admin/leads/${lead.id}`}
                    className="font-medium text-ink hover:text-brand-accent hover:underline"
                  >
                    {lead.first_name} {lead.last_name}
                  </Link>
                </div>
              </td>

              <td className="px-4 py-3">
                <a
                  href={`mailto:${lead.email}`}
                  className="text-sm text-ink-muted hover:text-brand-accent hover:underline"
                >
                  {lead.email}
                </a>
              </td>

              <td className="px-4 py-3">
                <StateBadge state={lead.state} />
              </td>

              <td className="px-4 py-3">
                <time
                  dateTime={lead.created_at}
                  title={new Date(lead.created_at).toLocaleString()}
                  className="text-sm text-ink-muted"
                >
                  {formatRelative(lead.created_at)}
                </time>
              </td>

              <td className="px-4 py-3 text-right">
                {lead.state === "PENDING" ? (
                  <MarkReachedOutButton leadId={lead.id} />
                ) : (
                  <span className="text-xs text-ink-subtle">
                    {lead.reached_out_by
                      ? `by ${lead.reached_out_by.full_name}`
                      : "Completed"}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="px-4 py-16 text-center">
      <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-surface-sunken">
        <svg
          className="h-5 w-5 text-ink-subtle"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"
          />
        </svg>
      </div>
      <p className="text-sm font-medium text-ink">No leads found</p>
      <p className="mt-1 text-sm text-ink-subtle">
        Try clearing your filters, or wait for a new submission to come in.
      </p>
    </div>
  );
}

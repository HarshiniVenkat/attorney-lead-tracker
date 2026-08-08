import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { MarkReachedOutButton } from "@/components/admin/mark-reached-out";
import { DeliveryBadge, StateBadge } from "@/components/ui/badge";
import { apiGet, ApiError } from "@/lib/api";
import type { LeadDetail } from "@/lib/types";
import { formatBytes, formatDateTime } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Lead detail",
};

const DELIVERY_LABELS: Record<string, string> = {
  PROSPECT_CONFIRMATION: "Confirmation to prospect",
  ATTORNEY_NOTIFICATION: "Notification to attorney",
};

export default async function LeadDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let lead: LeadDetail;
  try {
    lead = await apiGet<LeadDetail>(`/leads/${id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    throw error;
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/admin/leads"
          className="inline-flex items-center gap-1.5 text-sm text-ink-muted transition-colors hover:text-ink"
        >
          <span aria-hidden="true">←</span> Back to leads
        </Link>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight text-ink">
            {lead.first_name} {lead.last_name}
          </h1>
          <div className="flex flex-wrap items-center gap-3">
            <StateBadge state={lead.state} />
            <a
              href={`mailto:${lead.email}`}
              className="text-sm text-ink-muted hover:text-brand-accent hover:underline"
            >
              {lead.email}
            </a>
          </div>
        </div>

        {lead.state === "PENDING" && <MarkReachedOutButton leadId={lead.id} size="md" />}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Submission">
            <dl className="divide-y divide-line">
              <Row label="Full name">
                {lead.first_name} {lead.last_name}
              </Row>
              <Row label="Email">{lead.email}</Row>
              <Row label="Submitted">{formatDateTime(lead.created_at)}</Row>
              <Row label="Resume">
                <div className="flex flex-wrap items-center gap-2">
                  <a
                    href={`/api/leads/${lead.id}/resume`}
                    className="font-medium text-brand-accent hover:underline"
                  >
                    {lead.resume_filename}
                  </a>
                  <span className="text-xs text-ink-subtle">
                    ({formatBytes(lead.resume_size_bytes)})
                  </span>
                </div>
              </Row>
              {lead.reached_out_at && (
                <Row label="Reached out">
                  {formatDateTime(lead.reached_out_at)}
                  {lead.reached_out_by && (
                    <span className="text-ink-subtle"> by {lead.reached_out_by.full_name}</span>
                  )}
                </Row>
              )}
            </dl>
          </Card>

          <Card
            title="Email delivery"
            description="Status of the two emails sent when this lead was submitted."
          >
            <ul className="divide-y divide-line">
              {lead.email_deliveries.map((delivery) => (
                <li key={delivery.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink">
                      {DELIVERY_LABELS[delivery.kind] ?? delivery.kind}
                    </p>
                    <p className="truncate text-xs text-ink-subtle">{delivery.to_address}</p>
                    {delivery.last_error && (
                      <p className="mt-1 text-xs text-red-600">{delivery.last_error}</p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <DeliveryBadge status={delivery.status} />
                    <span className="text-xs text-ink-subtle">
                      {delivery.sent_at ? formatDateTime(delivery.sent_at) : "—"}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </div>

        <Card title="History" description="Every state change on this lead.">
          <ol className="space-y-4">
            {lead.state_events.map((event) => (
              <li key={event.id} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-line-strong" />
                  <span className="w-px flex-1 bg-line" />
                </div>
                <div className="pb-1">
                  <p className="text-sm text-ink">
                    {event.from_state ? (
                      <>
                        <span className="font-medium">{event.from_state}</span> →{" "}
                        <span className="font-medium">{event.to_state}</span>
                      </>
                    ) : (
                      <span className="font-medium">Submitted</span>
                    )}
                  </p>
                  <p className="text-xs text-ink-subtle">
                    {formatDateTime(event.created_at)}
                  </p>
                  <p className="text-xs text-ink-subtle">
                    {event.actor ? event.actor.full_name : "Prospect (public form)"}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </Card>
      </div>
    </div>
  );
}

function Card({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-line bg-white p-5 shadow-sm">
      <div className="mb-3">
        <h2 className="font-semibold text-ink">{title}</h2>
        {description && <p className="mt-0.5 text-sm text-ink-subtle">{description}</p>}
      </div>
      {children}
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap gap-1 py-2.5 sm:grid sm:grid-cols-3 sm:gap-4">
      <dt className="text-sm text-ink-subtle">{label}</dt>
      <dd className="text-sm text-ink sm:col-span-2">{children}</dd>
    </div>
  );
}

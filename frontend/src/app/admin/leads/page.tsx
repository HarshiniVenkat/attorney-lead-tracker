import type { Metadata } from "next";

import { LeadFilters } from "@/components/admin/lead-filters";
import { LeadsTable } from "@/components/admin/leads-table";
import { Pagination } from "@/components/admin/pagination";
import { Alert } from "@/components/ui/alert";
import { apiGet, ApiError } from "@/lib/api";
import type { Lead, Page } from "@/lib/types";

export const metadata: Metadata = {
  title: "Leads",
};

const PAGE_SIZE = 20;
const VALID_STATES = new Set(["PENDING", "REACHED_OUT"]);

interface SearchParams {
  state?: string;
  q?: string;
  page?: string;
}

export default async function LeadsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;

  // Sanitise before forwarding: the API rejects bad values with a 422, and a
  // hand-edited URL shouldn't turn into an error screen.
  const page = Math.max(1, Number.parseInt(params.page ?? "1", 10) || 1);
  const state = params.state && VALID_STATES.has(params.state) ? params.state : undefined;
  const q = params.q?.trim() || undefined;

  const query = new URLSearchParams({
    page: String(page),
    page_size: String(PAGE_SIZE),
  });
  if (state) query.set("state", state);
  if (q) query.set("q", q);

  let leads: Page<Lead>;
  let counts: Record<string, number>;

  try {
    [leads, counts] = await Promise.all([
      apiGet<Page<Lead>>(`/leads?${query.toString()}`),
      apiGet<Record<string, number>>("/leads/stats"),
    ]);
  } catch (error) {
    const message =
      error instanceof ApiError
        ? error.message
        : "We couldn't load leads right now. Please try again.";
    return (
      <div className="space-y-6">
        <PageHeading />
        <Alert tone="error">{message}</Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeading />

      <LeadFilters counts={counts} />

      <div className="overflow-hidden rounded-xl border border-line bg-white shadow-sm">
        <LeadsTable leads={leads.items} />
        <Pagination
          page={leads.page}
          totalPages={leads.total_pages}
          total={leads.total}
          pageSize={leads.page_size}
        />
      </div>
    </div>
  );
}

function PageHeading() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight text-ink">Leads</h1>
      <p className="mt-1 text-sm text-ink-muted">
        Prospects who submitted the public form. Mark a lead as reached out once
        you&apos;ve contacted them.
      </p>
    </div>
  );
}

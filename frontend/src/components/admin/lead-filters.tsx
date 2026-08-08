"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";
import type { LeadState } from "@/lib/types";

const TABS: { label: string; value: LeadState | "ALL" }[] = [
  { label: "All", value: "ALL" },
  { label: "Pending", value: "PENDING" },
  { label: "Reached out", value: "REACHED_OUT" },
];

interface Props {
  counts: Record<string, number>;
}

/**
 * Filter state lives in the URL, not component state, so a filtered view is
 * shareable, survives a refresh, and keeps the list a server component.
 */
export function LeadFilters({ counts }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const activeState = searchParams.get("state") ?? "ALL";
  const [search, setSearch] = useState(searchParams.get("q") ?? "");

  // Keep the input in sync when navigation changes the URL (back button).
  useEffect(() => {
    setSearch(searchParams.get("q") ?? "");
  }, [searchParams]);

  function pushParams(mutate: (params: URLSearchParams) => void) {
    const params = new URLSearchParams(searchParams.toString());
    mutate(params);
    // Any filter change invalidates the current page number.
    params.delete("page");
    router.push(`${pathname}?${params.toString()}`);
  }

  // Debounce so typing doesn't fire a request per keystroke.
  useEffect(() => {
    const current = searchParams.get("q") ?? "";
    if (search === current) return;

    const timer = setTimeout(() => {
      pushParams((params) => {
        if (search.trim()) params.set("q", search.trim());
        else params.delete("q");
      });
    }, 300);

    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const totalCount = (counts.PENDING ?? 0) + (counts.REACHED_OUT ?? 0);

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div
        role="tablist"
        aria-label="Filter leads by state"
        className="inline-flex rounded-lg border border-line bg-white p-1"
      >
        {TABS.map((tab) => {
          const isActive = activeState === tab.value;
          const count = tab.value === "ALL" ? totalCount : (counts[tab.value] ?? 0);

          return (
            <button
              key={tab.value}
              role="tab"
              aria-selected={isActive}
              onClick={() =>
                pushParams((params) => {
                  if (tab.value === "ALL") params.delete("state");
                  else params.set("state", tab.value);
                })
              }
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-brand text-white"
                  : "text-ink-muted hover:bg-surface-sunken hover:text-ink",
              )}
            >
              {tab.label}
              <span
                className={cn(
                  "ml-1.5 text-xs",
                  isActive ? "text-slate-300" : "text-ink-subtle",
                )}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      <div className="relative sm:w-72">
        <svg
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z"
          />
        </svg>
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search name or email"
          aria-label="Search leads"
          className={cn(
            "h-10 w-full rounded-lg border border-line-strong bg-white",
            "pl-9 pr-3 text-sm text-ink placeholder:text-ink-subtle",
            "transition-colors hover:border-slate-400",
          )}
        />
      </div>
    </div>
  );
}

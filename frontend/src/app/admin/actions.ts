"use server";

import { revalidatePath } from "next/cache";

import { apiFetch, toApiError } from "@/lib/api";
import type { LeadState } from "@/lib/types";

export interface ActionResult {
  ok: boolean;
  message?: string;
}

/**
 * Transition a lead's state.
 *
 * A server action rather than a client fetch: the session cookie is read
 * server-side, and revalidatePath refreshes the list and detail views from the
 * source of truth instead of trusting local component state.
 */
export async function updateLeadState(
  leadId: string,
  state: LeadState,
): Promise<ActionResult> {
  const response = await apiFetch(`/leads/${leadId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state }),
  });

  if (!response.ok) {
    const apiError = await toApiError(response);
    return { ok: false, message: apiError.message };
  }

  revalidatePath("/admin/leads");
  revalidatePath(`/admin/leads/${leadId}`);
  return { ok: true };
}

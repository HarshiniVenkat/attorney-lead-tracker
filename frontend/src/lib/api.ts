import "server-only";

import { redirect } from "next/navigation";

import { getSessionToken } from "@/lib/session";
import type { ApiErrorBody, FieldErrors } from "@/lib/types";

/**
 * Base URL for server-side calls. Inside Docker the API is reachable as
 * `backend:8000`; from the host it is `localhost:8000`.
 */
export const API_BASE_URL =
  process.env.API_BASE_URL ?? "http://localhost:8000";

export const API_V1 = `${API_BASE_URL}/api/v1`;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fieldErrors: FieldErrors;

  constructor(status: number, code: string, message: string, fieldErrors: FieldErrors = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fieldErrors = fieldErrors;
  }
}

/** Parse the backend's error envelope; fall back gracefully if it isn't one. */
export async function toApiError(response: Response): Promise<ApiError> {
  let code = "unknown_error";
  let message = `Request failed with status ${response.status}.`;
  let fieldErrors: FieldErrors = {};

  try {
    const body = (await response.json()) as ApiErrorBody;
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
      fieldErrors = (body.error.details?.fields as FieldErrors) ?? {};
    }
  } catch {
    // Non-JSON body (proxy error page, empty 502). Keep the generic message.
  }

  return new ApiError(response.status, code, message, fieldErrors);
}

/**
 * Authenticated server-side fetch.
 *
 * The JWT never reaches the browser as a readable value: it lives in an
 * httpOnly cookie, is read here on the server, and is forwarded as a Bearer
 * header. A 401 means the token expired or the account was deactivated, so we
 * bounce to the login page rather than rendering a broken screen.
 */
export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const token = await getSessionToken();
  if (!token) {
    redirect("/admin/login");
  }

  const response = await fetch(`${API_V1}${path}`, {
    ...init,
    headers: {
      ...init.headers,
      Authorization: `Bearer ${token}`,
    },
    // Lead data changes as attorneys work; never serve it from a cache.
    cache: "no-store",
  });

  if (response.status === 401) {
    redirect("/admin/login?reason=expired");
  }

  return response;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await apiFetch(path);
  if (!response.ok) {
    throw await toApiError(response);
  }
  return (await response.json()) as T;
}

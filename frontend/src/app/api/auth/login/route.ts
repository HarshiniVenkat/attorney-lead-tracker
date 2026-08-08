import { NextResponse } from "next/server";

import { API_V1, toApiError } from "@/lib/api";
import { SESSION_COOKIE, sessionCookieOptions } from "@/lib/session";

/**
 * Credential exchange.
 *
 * The browser posts here rather than to FastAPI directly so the JWT can be
 * written into an httpOnly cookie server-side. The token is never exposed to
 * client JavaScript, which is what keeps an XSS bug from becoming a stolen
 * session.
 */
export async function POST(request: Request) {
  let payload: { email?: string; password?: string };
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json(
      { error: { code: "bad_request", message: "Invalid request body." } },
      { status: 400 },
    );
  }

  const response = await fetch(`${API_V1}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: payload.email, password: payload.password }),
    cache: "no-store",
  });

  if (!response.ok) {
    const apiError = await toApiError(response);
    return NextResponse.json(
      { error: { code: apiError.code, message: apiError.message } },
      { status: apiError.status },
    );
  }

  const { access_token, expires_in } = (await response.json()) as {
    access_token: string;
    expires_in: number;
  };

  const result = NextResponse.json({ ok: true });
  result.cookies.set(SESSION_COOKIE, access_token, sessionCookieOptions(expires_in));
  return result;
}

import { NextResponse } from "next/server";

import { SESSION_COOKIE } from "@/lib/session";

/**
 * Clear the session cookie.
 *
 * The JWT itself stays valid until it expires - this is a stateless token, so
 * there is nothing server-side to revoke. Dropping the cookie is what ends the
 * session for this browser. Immediate revocation would need a token blocklist
 * or short-lived tokens plus refresh; see SYSTEM_OVERVIEW.md.
 */
export async function POST() {
  const response = NextResponse.json({ ok: true });
  response.cookies.set(SESSION_COOKIE, "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  return response;
}

import "server-only";

import { cookies } from "next/headers";

export const SESSION_COOKIE = process.env.SESSION_COOKIE_NAME ?? "alma_session";

/**
 * Cookie options for the session token.
 *
 * httpOnly keeps the JWT out of reach of any script on the page, so an XSS bug
 * cannot exfiltrate it. sameSite=lax blocks it from riding along on
 * cross-site POSTs (CSRF) while still surviving a normal top-level navigation
 * back into the app.
 */
export function sessionCookieOptions(maxAgeSeconds: number) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: maxAgeSeconds,
  };
}

export async function getSessionToken(): Promise<string | undefined> {
  const store = await cookies();
  return store.get(SESSION_COOKIE)?.value;
}

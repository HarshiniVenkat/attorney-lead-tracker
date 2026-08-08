import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = process.env.SESSION_COOKIE_NAME ?? "alma_session";

/**
 * Route guard for the internal UI.
 *
 * This is a cheap presence check on the cookie, not a verification of the
 * token. It exists to avoid rendering an admin shell for someone who is
 * plainly signed out. Real enforcement happens in FastAPI, which validates the
 * signature and re-checks the account on every request - so a forged cookie
 * gets past this redirect and straight into a 401.
 */
export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value);

  if (pathname === "/admin" || pathname === "/admin/") {
    return NextResponse.redirect(new URL("/admin/leads", request.url));
  }

  const isLoginPage = pathname.startsWith("/admin/login");

  if (!hasSession && !isLoginPage) {
    const loginUrl = new URL("/admin/login", request.url);
    // Remember where they were headed so login can send them back.
    loginUrl.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(loginUrl);
  }

  if (hasSession && isLoginPage) {
    return NextResponse.redirect(new URL("/admin/leads", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*"],
};

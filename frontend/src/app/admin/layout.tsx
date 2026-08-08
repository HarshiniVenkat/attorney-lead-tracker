import Link from "next/link";

import { SignOutButton } from "@/components/admin/sign-out-button";
import { apiGet } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import type { CurrentUser } from "@/lib/types";

/**
 * Shell for the internal UI.
 *
 * The login page renders inside this layout too, so the header is only shown
 * once a session exists - otherwise a signed-out visitor would see a "Sign
 * out" control.
 */
export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const token = await getSessionToken();

  if (!token) {
    return <>{children}</>;
  }

  let user: CurrentUser | null = null;
  try {
    user = await apiGet<CurrentUser>("/auth/me");
  } catch {
    // A failed /auth/me shouldn't blank the page; apiFetch already redirects
    // on a 401, so this is a transient backend problem.
    user = null;
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <Link href="/admin/leads" className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-sm font-semibold text-white">
                A
              </span>
              <span className="font-semibold tracking-tight text-ink">
                Lead dashboard
              </span>
            </Link>
          </div>

          <div className="flex items-center gap-4">
            {user && (
              <div className="hidden text-right sm:block">
                <p className="text-sm font-medium leading-tight text-ink">
                  {user.full_name}
                </p>
                <p className="text-xs leading-tight text-ink-subtle">{user.email}</p>
              </div>
            )}
            <SignOutButton />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">{children}</main>
    </div>
  );
}

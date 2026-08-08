import type { Metadata } from "next";

import { LoginForm } from "@/components/admin/login-form";

export const metadata: Metadata = {
  title: "Sign in",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; reason?: string }>;
}) {
  const params = await searchParams;

  // Only accept same-origin relative paths: an attacker-supplied absolute URL
  // here would turn the login page into an open redirect.
  const requested = params.next ?? "";
  const next =
    requested.startsWith("/") && !requested.startsWith("//")
      ? requested
      : "/admin/leads";

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-brand">
            <span className="text-lg font-semibold text-white">A</span>
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">
            Internal lead dashboard
          </h1>
          <p className="mt-1 text-sm text-ink-muted">
            Sign in with your attorney account.
          </p>
        </div>

        <div className="rounded-2xl border border-line bg-white p-6 shadow-sm">
          <LoginForm next={next} expired={params.reason === "expired"} />
        </div>
      </div>
    </main>
  );
}

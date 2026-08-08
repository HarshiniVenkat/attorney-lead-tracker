import type { Metadata } from "next";

import { LeadForm } from "@/components/apply/lead-form";

export const metadata: Metadata = {
  title: "Get an assessment",
  description: "Submit your details and resume for a free case assessment.",
};

export default function ApplyPage() {
  return (
    <main className="min-h-screen">
      <section className="bg-brand px-4 py-14 text-center sm:py-20">
        <div className="mx-auto max-w-2xl space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
            Alma · Immigration
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Get an assessment of your immigration case
          </h1>
          <p className="mx-auto max-w-lg text-base leading-relaxed text-slate-300">
            Share a few details and your resume. One of our attorneys will review your
            background and get back to you with the visa options available to you.
          </p>
        </div>
      </section>

      <section className="px-4 pb-20">
        {/* Pulled up over the banner so the form is the visual focus. */}
        <div className="mx-auto -mt-8 max-w-xl rounded-2xl border border-line bg-white p-6 shadow-sm sm:p-8">
          <div className="mb-6 space-y-1">
            <h2 className="text-lg font-semibold text-ink">Submit your information</h2>
            <p className="text-sm text-ink-muted">
              All fields are required. It takes about a minute.
            </p>
          </div>

          <LeadForm />
        </div>
      </section>
    </main>
  );
}

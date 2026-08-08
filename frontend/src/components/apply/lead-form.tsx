"use client";

import { useState, type FormEvent } from "react";

import { FileDropzone, validateResume } from "@/components/apply/file-dropzone";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import type { ApiErrorBody, FieldErrors } from "@/lib/types";

/**
 * The browser talks to the API directly here rather than through a Next route
 * handler: this endpoint is public, so there is no token to attach, and
 * streaming the file straight to the API avoids buffering it through an extra
 * hop.
 */
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

interface FormValues {
  first_name: string;
  last_name: string;
  email: string;
}

const EMPTY: FormValues = { first_name: "", last_name: "", email: "" };

export function LeadForm() {
  const [values, setValues] = useState<FormValues>(EMPTY);
  const [file, setFile] = useState<File | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  function update(field: keyof FormValues, value: string) {
    setValues((prev) => ({ ...prev, [field]: value }));
    // Clear a field's error as soon as the user edits it: keeping stale red
    // text under a field they are actively fixing reads as broken.
    setFieldErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }

  function validate(): FieldErrors {
    const errors: FieldErrors = {};

    if (!values.first_name.trim()) errors.first_name = "First name is required.";
    if (!values.last_name.trim()) errors.last_name = "Last name is required.";

    if (!values.email.trim()) {
      errors.email = "Email is required.";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim())) {
      errors.email = "Enter a valid email address.";
    }

    if (!file) {
      errors.resume = "Please attach your resume.";
    } else {
      const fileError = validateResume(file);
      if (fileError) errors.resume = fileError;
    }

    return errors;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    const errors = validate();
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setSubmitting(true);
    try {
      const body = new FormData();
      body.append("first_name", values.first_name.trim());
      body.append("last_name", values.last_name.trim());
      body.append("email", values.email.trim());
      body.append("resume", file as File);

      const response = await fetch(`${API_BASE_URL}/api/v1/leads`, {
        method: "POST",
        body,
      });

      if (response.ok) {
        setSubmitted(true);
        return;
      }

      const payload = (await response.json().catch(() => null)) as ApiErrorBody | null;
      const serverFields = payload?.error?.details?.fields as FieldErrors | undefined;

      if (serverFields && Object.keys(serverFields).length > 0) {
        setFieldErrors(serverFields);
      } else {
        setFormError(
          payload?.error?.message ?? "Something went wrong. Please try again.",
        );
      }
    } catch {
      setFormError("We couldn't reach the server. Check your connection and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return <ThankYou firstName={values.first_name.trim()} />;
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      {formError && <Alert tone="error">{formError}</Alert>}

      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="First name" htmlFor="first_name" error={fieldErrors.first_name} required>
          <Input
            id="first_name"
            name="first_name"
            autoComplete="given-name"
            placeholder="Ada"
            value={values.first_name}
            invalid={Boolean(fieldErrors.first_name)}
            disabled={submitting}
            onChange={(event) => update("first_name", event.target.value)}
          />
        </Field>

        <Field label="Last name" htmlFor="last_name" error={fieldErrors.last_name} required>
          <Input
            id="last_name"
            name="last_name"
            autoComplete="family-name"
            placeholder="Lovelace"
            value={values.last_name}
            invalid={Boolean(fieldErrors.last_name)}
            disabled={submitting}
            onChange={(event) => update("last_name", event.target.value)}
          />
        </Field>
      </div>

      <Field label="Email" htmlFor="email" error={fieldErrors.email} required>
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="ada@example.com"
          value={values.email}
          invalid={Boolean(fieldErrors.email)}
          disabled={submitting}
          onChange={(event) => update("email", event.target.value)}
        />
      </Field>

      <Field
        label="Resume / CV"
        htmlFor="resume"
        error={fieldErrors.resume}
        hint="We accept PDF and DOCX files up to 5 MB."
        required
      >
        <FileDropzone
          file={file}
          disabled={submitting}
          error={fieldErrors.resume}
          onChange={(next) => {
            setFile(next);
            setFieldErrors((prev) => {
              if (!prev.resume) return prev;
              const rest = { ...prev };
              delete rest.resume;
              return rest;
            });
          }}
        />
      </Field>

      <Button type="submit" size="lg" loading={submitting} className="w-full">
        {submitting ? "Submitting…" : "Submit application"}
      </Button>

      <p className="text-center text-xs text-ink-subtle">
        By submitting, you agree to be contacted about your application.
      </p>
    </form>
  );
}

function ThankYou({ firstName }: { firstName: string }) {
  return (
    <div className="animate-fade-in space-y-4 py-6 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50 ring-1 ring-emerald-200">
        <svg
          className="h-7 w-7 text-emerald-600"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
        </svg>
      </div>

      <div className="space-y-2">
        <h2 className="text-xl font-semibold text-ink">
          Thank you{firstName ? `, ${firstName}` : ""}!
        </h2>
        <p className="mx-auto max-w-sm text-sm leading-relaxed text-ink-muted">
          Your application is in. We&apos;ve emailed you a confirmation, and one of our
          attorneys will review your submission and reach out with next steps.
        </p>
      </div>

      <p className="text-sm text-ink-subtle">
        Nothing further is needed from you right now.
      </p>
    </div>
  );
}

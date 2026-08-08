import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, invalid, ...props }, ref) => (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        "h-11 w-full rounded-lg border bg-white px-3 text-sm text-ink",
        "placeholder:text-ink-subtle transition-colors",
        "disabled:cursor-not-allowed disabled:bg-surface-sunken",
        invalid
          ? "border-red-400 focus-visible:ring-red-500"
          : "border-line-strong hover:border-slate-400",
        className,
      )}
      {...props}
    />
  ),
);

Input.displayName = "Input";

interface FieldProps {
  label: string;
  htmlFor: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
}

/**
 * Label + control + message. The error is wired to the control via
 * aria-describedby so screen readers announce it, and uses role="alert" so it
 * is announced when it appears.
 */
export function Field({ label, htmlFor, error, hint, required, children }: FieldProps) {
  const describedBy = error ? `${htmlFor}-error` : hint ? `${htmlFor}-hint` : undefined;

  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-ink">
        {label}
        {required && (
          <span className="ml-0.5 text-red-600" aria-hidden="true">
            *
          </span>
        )}
      </label>

      <div aria-describedby={describedBy}>{children}</div>

      {error ? (
        <p id={`${htmlFor}-error`} role="alert" className="text-sm text-red-600">
          {error}
        </p>
      ) : hint ? (
        <p id={`${htmlFor}-hint`} className="text-sm text-ink-subtle">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

"use client";

import { useId, useRef, useState, type DragEvent } from "react";

import { cn, formatBytes } from "@/lib/utils";

const ACCEPTED_EXTENSIONS = [".pdf", ".docx"];
const ACCEPT_ATTRIBUTE =
  ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";
export const MAX_RESUME_BYTES = 5 * 1024 * 1024;

interface FileDropzoneProps {
  file: File | null;
  onChange: (file: File | null) => void;
  error?: string;
  disabled?: boolean;
}

/**
 * Client-side checks here are for fast feedback only. The server re-validates
 * by sniffing magic bytes, which is the check that actually counts.
 */
export function validateResume(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))) {
    return "Resume must be a PDF or DOCX file.";
  }
  if (file.size > MAX_RESUME_BYTES) {
    return "Resume must be smaller than 5 MB.";
  }
  if (file.size === 0) {
    return "That file appears to be empty.";
  }
  return null;
}

export function FileDropzone({ file, onChange, error, disabled }: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const inputId = useId();

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    if (disabled) return;

    const dropped = event.dataTransfer.files?.[0];
    if (dropped) onChange(dropped);
  }

  function clearFile() {
    onChange(null);
    // Reset the input, otherwise re-selecting the same filename fires no
    // change event and the field silently stays empty.
    if (inputRef.current) inputRef.current.value = "";
  }

  if (file) {
    return (
      <div
        className={cn(
          "flex items-center gap-3 rounded-lg border border-line-strong",
          "bg-surface-sunken px-4 py-3",
          error && "border-red-400",
        )}
      >
        <svg
          className="h-8 w-8 shrink-0 text-ink-subtle"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25M9 16.5v.75m3-3v3M15 12v5.25M6.75 21h10.5a2.25 2.25 0 002.25-2.25V11.25a9 9 0 00-9-9H6.75A2.25 2.25 0 004.5 4.5v14.25A2.25 2.25 0 006.75 21z"
          />
        </svg>

        <div className="min-w-0 flex-1">
          {/* truncate + min-w-0 so a very long filename can't blow out the layout */}
          <p className="truncate text-sm font-medium text-ink">{file.name}</p>
          <p className="text-xs text-ink-subtle">{formatBytes(file.size)}</p>
        </div>

        <button
          type="button"
          onClick={clearFile}
          disabled={disabled}
          className={cn(
            "shrink-0 rounded-md px-2.5 py-1.5 text-sm font-medium",
            "text-ink-muted transition-colors hover:bg-white hover:text-ink",
            "disabled:cursor-not-allowed disabled:opacity-50",
          )}
        >
          Remove
        </button>
      </div>
    );
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      className={cn(
        "rounded-lg border-2 border-dashed transition-colors",
        isDragging ? "border-brand-accent bg-blue-50" : "border-line-strong bg-white",
        error && "border-red-400",
        disabled && "opacity-60",
      )}
    >
      <label
        htmlFor={inputId}
        className={cn(
          "flex cursor-pointer flex-col items-center gap-2 px-6 py-8 text-center",
          disabled && "cursor-not-allowed",
        )}
      >
        <svg
          className="h-9 w-9 text-ink-subtle"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 16.5V9.75m0 0l-3 3m3-3l3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z"
          />
        </svg>

        <span className="text-sm font-medium text-ink">
          <span className="text-brand-accent underline underline-offset-2">
            Click to upload
          </span>{" "}
          or drag and drop
        </span>
        <span className="text-xs text-ink-subtle">PDF or DOCX, up to 5 MB</span>

        <input
          ref={inputRef}
          id={inputId}
          type="file"
          name="resume"
          accept={ACCEPT_ATTRIBUTE}
          disabled={disabled}
          className="sr-only"
          onChange={(event) => onChange(event.target.files?.[0] ?? null)}
        />
      </label>
    </div>
  );
}

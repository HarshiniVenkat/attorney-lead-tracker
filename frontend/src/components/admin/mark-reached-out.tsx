"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { updateLeadState } from "@/app/admin/actions";
import { Button } from "@/components/ui/button";

interface Props {
  leadId: string;
  size?: "sm" | "md";
}

export function MarkReachedOutButton({ leadId, size = "sm" }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function handleClick() {
    setError(null);
    startTransition(async () => {
      const result = await updateLeadState(leadId, "REACHED_OUT");
      if (result.ok) {
        router.refresh();
      } else {
        // Surface the server's reason (e.g. a 409 from a concurrent edit)
        // rather than silently leaving the row unchanged.
        setError(result.message ?? "Could not update this lead.");
      }
    });
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        size={size}
        variant="secondary"
        loading={isPending}
        onClick={handleClick}
      >
        {isPending ? "Updating…" : "Mark as reached out"}
      </Button>
      {error && (
        <span role="alert" className="text-xs text-red-600">
          {error}
        </span>
      )}
    </div>
  );
}

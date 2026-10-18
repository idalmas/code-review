"use client";

import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api";
import type { FileSummary, Tier } from "@/lib/types";

import { SignInButton } from "../SignInButton";

interface Props {
  path: string;
  tier: Tier;
  summarize: (path: string, tier: Tier) => Promise<FileSummary>;
  /** Already-fetched summary for this file, if any (survives switching files). */
  cached: (path: string, tier: Tier) => Promise<FileSummary> | undefined;
}

export function FileSummaryPanel({ path, tier, summarize, cached }: Props) {
  // Summaries are kept per file+tier; one fetched for another tier isn't shown.
  const [result, setResult] = useState<{
    key: string;
    summary: FileSummary;
  } | null>(null);
  const key = `${tier}:${path}`;
  const summary = result?.key === key ? result.summary : null;
  const [error, setError] = useState<Error | null>(null);
  const [pending, setPending] = useState(false);

  // Show a summary we already paid for when coming back to this file or tier.
  useEffect(() => {
    let cancelled = false;
    cached(path, tier)?.then(
      (s) => !cancelled && setResult({ key: `${tier}:${path}`, summary: s }),
      () => {},
    );
    return () => {
      cancelled = true;
    };
  }, [path, tier, cached]);

  async function run() {
    setPending(true);
    setError(null);
    try {
      setResult({ key, summary: await summarize(path, tier) });
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={run}
        disabled={pending}
        className="rounded-md border border-border px-2 py-0.5 text-xs font-medium hover:bg-selected disabled:opacity-50"
      >
        {pending ? "Summarizing…" : summary ? "Summarize again" : "Summarize"}
      </button>
      <ErrorNote error={error} />
      {summary && (
        <div className="space-y-1">
          {/* Rendered as plain text: model output is never interpreted as HTML. */}
          <p className="whitespace-pre-wrap leading-6">{summary.text}</p>
        </div>
      )}
    </div>
  );
}

export function ErrorNote({ error }: { error: Error | null }) {
  if (!error) return null;
  return (
    <div className="space-y-2 text-del-fg">
      <p>{error.message}</p>
      {error instanceof ApiError && error.code === "sign_in_required" && (
        <SignInButton />
      )}
    </div>
  );
}

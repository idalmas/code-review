"use client";

import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api";
import type { FileSummary, LLMStatus, Tier } from "@/lib/types";
import { useTier } from "@/lib/useTier";

import { SignInButton } from "../SignInButton";

interface Props {
  path: string;
  status: LLMStatus;
  summarize: (path: string, tier: Tier) => Promise<FileSummary>;
  /** Already-fetched summary for this file, if any (survives switching files). */
  cached: (path: string, tier: Tier) => Promise<FileSummary> | undefined;
}

export function FileSummaryPanel({ path, status, summarize, cached }: Props) {
  const [tier, setTier] = useTier(status.default_tier);
  const [summary, setSummary] = useState<FileSummary | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [pending, setPending] = useState(false);

  // Show a summary we already paid for when coming back to this file.
  useEffect(() => {
    let cancelled = false;
    cached(path, tier)?.then(
      (s) => !cancelled && setSummary(s),
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
      setSummary(await summarize(path, tier));
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setPending(false);
    }
  }

  const tierInfo = status.tiers.find((t) => t.tier === tier);

  return (
    <div className="border-b border-border px-4 py-2 text-sm">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={run}
          disabled={pending}
          className="rounded-md border border-border px-2 py-0.5 text-xs font-medium hover:bg-selected disabled:opacity-50"
        >
          {pending ? "Summarizing…" : summary ? "Summarize again" : "✨ Summarize change"}
        </button>
        <div role="radiogroup" aria-label="AI tier" className="flex overflow-hidden rounded-md border border-border text-xs">
          {status.tiers.map((t) => (
            <button
              key={t.tier}
              type="button"
              role="radio"
              aria-checked={tier === t.tier}
              title={`${t.description} (${t.model})`}
              onClick={() => {
                setTier(t.tier);
                setSummary(null);
              }}
              className={`px-2 py-0.5 ${tier === t.tier ? "bg-accent text-white" : "hover:bg-selected"}`}
            >
              {t.label}
            </button>
          ))}
        </div>
        {tierInfo && <span className="text-xs text-muted">{tierInfo.model}</span>}
      </div>

      {error && (
        <div className="mt-2 space-y-2 text-del-fg">
          <p>{error.message}</p>
          {error instanceof ApiError && error.code === "sign_in_required" && <SignInButton />}
        </div>
      )}
      {summary && (
        <div className="mt-2 space-y-1">
          {/* Rendered as plain text: model output is never interpreted as HTML. */}
          <p className="whitespace-pre-wrap leading-6">{summary.text}</p>
          <p className="text-xs text-muted">
            {summary.model} · {summary.input_tokens.toLocaleString()} in /{" "}
            {summary.output_tokens.toLocaleString()} out tokens
            {summary.truncated && " · cut short at the length limit"}
          </p>
        </div>
      )}
    </div>
  );
}

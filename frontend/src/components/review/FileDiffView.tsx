"use client";

import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api";
import type {
  DiffLine,
  FileDiff,
  FileSummary,
  Hunk,
  LLMStatus,
  RenderJob,
  ReviewFile,
  StressJob,
  Tier,
} from "@/lib/types";
import { useTier } from "@/lib/useTier";

import { FileSummaryPanel } from "./FileSummaryPanel";
import { RenderPanel } from "./RenderPanel";
import { StressPanel } from "./StressPanel";
import { TierPicker } from "./TierPicker";

// Same rule as the backend: component files, not tests or stories.
const isComponentFile = (path: string) =>
  /\.(tsx|jsx)$/.test(path) && !/\.(test|spec|stories)\.[jt]sx$/.test(path);
const isBackendFile = (path: string) =>
  /\.(py|ts|mts|js|mjs)$/.test(path) &&
  !/\.d\.ts$/.test(path) &&
  !/(^|\/)(test_[^/]*\.py|[^/]*_test\.py|[^/]*\.(test|spec)\.[mc]?[jt]s)$/.test(
    path,
  );

interface Props {
  file: ReviewFile;
  viewed: boolean;
  onToggleViewed: () => void;
  loadDiff: (path: string) => Promise<FileDiff>;
  llm: LLMStatus | null;
  summarize: (path: string, tier: Tier) => Promise<FileSummary>;
  cachedSummary: (path: string, tier: Tier) => Promise<FileSummary> | undefined;
  renderEnabled: boolean;
  startRender: (path: string, tier: Tier) => Promise<RenderJob>;
  renderJobFor: (path: string) => string | undefined;
  stressEnabled: boolean;
  startStress: (path: string, tier: Tier) => Promise<StressJob>;
  stressJobFor: (path: string) => string | undefined;
}

export function FileDiffView({
  file,
  viewed,
  onToggleViewed,
  loadDiff,
  llm,
  summarize,
  cachedSummary,
  renderEnabled,
  startRender,
  renderJobFor,
  stressEnabled,
  startStress,
  stressJobFor,
}: Props) {
  const [tier, setTier] = useTier(llm?.default_tier ?? "cheap");
  const [diff, setDiff] = useState<FileDiff | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadDiff(file.path).then(
      (d) => !cancelled && setDiff(d),
      (err) =>
        !cancelled &&
        setError(err instanceof ApiError ? err.message : String(err)),
    );
    return () => {
      cancelled = true;
    };
  }, [file.path, loadDiff]);

  return (
    <article>
      <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-panel px-4 py-2 text-sm">
        <span className="truncate font-mono">
          {file.previous_path && file.previous_path !== file.path && (
            <span className="text-muted">{file.previous_path} → </span>
          )}
          {file.path}
        </span>
        <span className="shrink-0 font-mono text-xs">
          <span className="text-add-fg">+{file.additions}</span>{" "}
          <span className="text-del-fg">−{file.deletions}</span>
        </span>
        <a
          href={file.github_url}
          target="_blank"
          rel="noreferrer"
          className="ml-auto shrink-0 text-xs text-accent hover:underline"
        >
          GitHub ↗
        </a>
        <label className="flex shrink-0 cursor-pointer items-center gap-1 text-xs">
          <input type="checkbox" checked={viewed} onChange={onToggleViewed} />
          Viewed <kbd>v</kbd>
        </label>
      </div>

      {llm?.enabled && file.has_diff && (
        <div className="space-y-3 border-b border-border px-4 py-2 text-sm">
          <TierPicker status={llm} tier={tier} onChange={setTier} />
          <FileSummaryPanel
            path={file.path}
            tier={tier}
            summarize={summarize}
            cached={cachedSummary}
          />
          {renderEnabled && isComponentFile(file.path) && (
            <RenderPanel
              path={file.path}
              tier={tier}
              start={startRender}
              jobIdFor={renderJobFor}
            />
          )}
          {stressEnabled && isBackendFile(file.path) && (
            <StressPanel
              path={file.path}
              tier={tier}
              start={startStress}
              jobIdFor={stressJobFor}
            />
          )}
        </div>
      )}

      {error && <p className="p-4 text-del-fg">{error}</p>}
      {!diff && !error && <p className="p-4 text-muted">Loading diff…</p>}
      {diff?.unavailable_reason && (
        <p className="p-4 text-muted">
          {diff.unavailable_reason === "too_large"
            ? "GitHub doesn't send diffs this large. "
            : "Binary or empty file. "}
          <a
            href={file.github_url}
            target="_blank"
            rel="noreferrer"
            className="text-accent"
          >
            View it on GitHub
          </a>
          .
        </p>
      )}
      {diff && (
        <div className="font-mono text-xs leading-5">
          {diff.hunks.map((hunk, i) => (
            <HunkView key={i} hunk={hunk} />
          ))}
        </div>
      )}
    </article>
  );
}

function HunkView({ hunk }: { hunk: Hunk }) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    // content-visibility lets the browser skip layout for off-screen hunks in huge files.
    <section className="[content-visibility:auto]">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="block w-full bg-hunk-bg px-4 py-1 text-left text-muted"
      >
        {collapsed ? "▸" : "▾"} {hunk.header}
      </button>
      {!collapsed &&
        hunk.lines.map((line, i) => <LineRow key={i} line={line} />)}
    </section>
  );
}

const ROW_STYLE: Record<
  DiffLine["kind"],
  { row: string; num: string; sign: string }
> = {
  add: { row: "bg-add-bg", num: "bg-add-num", sign: "+" },
  del: { row: "bg-del-bg", num: "bg-del-num", sign: "-" },
  context: { row: "", num: "", sign: " " },
  meta: { row: "text-muted italic", num: "", sign: "" },
};

function LineRow({ line }: { line: DiffLine }) {
  const style = ROW_STYLE[line.kind];
  return (
    <div className={`grid grid-cols-[3.5rem_3.5rem_1fr] ${style.row}`}>
      <span className={`select-none pr-2 text-right text-muted ${style.num}`}>
        {line.old_number ?? ""}
      </span>
      <span className={`select-none pr-2 text-right text-muted ${style.num}`}>
        {line.new_number ?? ""}
      </span>
      <span className="whitespace-pre-wrap break-all pl-2">
        <span className="select-none">{style.sign}</span>
        {line.content}
      </span>
    </div>
  );
}

"use client";

import { useState } from "react";

import { api, renderImageUrl } from "@/lib/api";
import type { RenderJob, RenderState, Tier } from "@/lib/types";
import { useJob } from "@/lib/useJob";

import { ErrorNote } from "./FileSummaryPanel";
import { LiveInspector, type PickTarget } from "./LiveInspector";

export interface RenderComments {
  resolve: (chain: string[]) => Promise<PickTarget | null>;
  comment: (target: PickTarget, body: string) => Promise<unknown>;
  onJump: (path: string) => void;
}

const RUNNING: RenderJob["status"][] = [
  "queued",
  "downloading",
  "writing_harness",
  "installing",
  "rendering",
];
const STEP_LABEL: Partial<Record<RenderJob["status"], string>> = {
  queued: "Queued…",
  downloading: "Downloading both versions…",
  installing: "Installing dependencies in the sandbox…",
  writing_harness: "Writing test states…",
  rendering: "Rendering before and after…",
};

interface Props {
  path: string;
  tier: Tier;
  start: (path: string, tier: Tier) => Promise<RenderJob>;
  /** Job id previously started for this file, so results survive switching files. */
  jobIdFor: (path: string) => string | undefined;
  comments: RenderComments;
}

export function RenderPanel({ path, tier, start, jobIdFor, comments }: Props) {
  const { job, setJob, error, setError, isRunning } = useJob(
    api.getRender,
    RUNNING,
    jobIdFor(path),
  );

  async function run() {
    setError(null);
    try {
      setJob(await start(path, tier));
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={run}
          disabled={isRunning}
          className="rounded-md border border-border px-2 py-0.5 text-xs font-medium hover:bg-selected disabled:opacity-50"
        >
          {job && !isRunning ? "Render again" : "🖼 Render before / after"}
        </button>
        {job && isRunning && (
          <span className="text-xs text-muted">{STEP_LABEL[job.status]}</span>
        )}
      </div>
      <ErrorNote error={error} />
      {job?.message && (
        <p className={job.status === "failed" ? "text-del-fg" : "text-muted"}>
          {job.status === "skipped" ? "Not rendered: " : ""}
          <span className="whitespace-pre-wrap">{job.message}</span>
        </p>
      )}
      {job?.states.map((state, i) => (
        <StateRow
          key={i}
          jobId={job.id}
          livePath={job.live_path}
          index={i}
          state={state}
          comments={comments}
        />
      ))}
    </div>
  );
}

function StateRow({
  jobId,
  livePath,
  index,
  state,
  comments,
}: {
  jobId: string;
  livePath: string | null;
  index: number;
  state: RenderState;
  comments: RenderComments;
}) {
  const [live, setLive] = useState(false);
  return (
    <section className="space-y-1">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-medium">{state.name}</span>
        <span className="text-muted">
          {state.viewport.width}×{state.viewport.height}
        </span>
        {state.base && state.head && !state.changed && (
          <span className="text-muted">· no visual change</span>
        )}
        {state.problems.map((p) => (
          <span key={p} className="rounded bg-del-bg px-1.5 text-del-fg">
            {p}
          </span>
        ))}
        {livePath && state.head && (
          <button
            type="button"
            onClick={() => setLive(!live)}
            className="ml-auto rounded-md border border-border px-2 py-0.5 hover:bg-selected"
          >
            {live ? "Close live view" : "💬 Click to comment"}
          </button>
        )}
      </div>
      {live && livePath && (
        <LiveInspector
          livePath={livePath}
          index={index}
          state={state}
          resolve={comments.resolve}
          comment={comments.comment}
          onJump={comments.onJump}
        />
      )}
      <div className="grid grid-cols-2 gap-3">
        <Shot
          jobId={jobId}
          index={index}
          version="base"
          label="Before"
          shot={state.base}
        />
        <Shot
          jobId={jobId}
          index={index}
          version="head"
          label="After"
          shot={state.head}
        />
      </div>
    </section>
  );
}

function Shot({
  jobId,
  index,
  version,
  label,
  shot,
}: {
  jobId: string;
  index: number;
  version: "base" | "head";
  label: string;
  shot: RenderState["base"];
}) {
  return (
    <figure className="min-w-0 space-y-1">
      <figcaption className="text-xs text-muted">{label}</figcaption>
      {shot ? (
        <>
          <a
            href={renderImageUrl(jobId, version, index)}
            target="_blank"
            rel="noreferrer"
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API image */}
            <img
              src={renderImageUrl(jobId, version, index)}
              alt={`${label}: rendered component`}
              className="max-w-full rounded border border-border bg-white"
            />
          </a>
          {shot.errors.length > 0 && (
            <pre className="max-h-32 overflow-auto rounded bg-del-bg p-2 text-xs whitespace-pre-wrap text-del-fg">
              {shot.errors.slice(0, 3).join("\n\n")}
            </pre>
          )}
        </>
      ) : (
        <p className="text-xs text-muted">
          {version === "base" ? "New in this PR" : "Removed in this PR"}
        </p>
      )}
    </figure>
  );
}

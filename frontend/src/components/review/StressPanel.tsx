"use client";

import { api } from "@/lib/api";
import type { StressJob, Tier } from "@/lib/types";
import { useJob } from "@/lib/useJob";

import { ErrorNote } from "./FileSummaryPanel";

const RUNNING: StressJob["status"][] = [
  "queued",
  "downloading",
  "installing",
  "writing_tests",
  "running",
];
const STEP_LABEL: Partial<Record<StressJob["status"], string>> = {
  queued: "Queued…",
  downloading: "Downloading both versions…",
  installing: "Installing dependencies in the sandbox…",
  writing_tests: "Writing stress tests…",
  running: "Running tests before and after…",
};
const VERDICT: Record<
  NonNullable<StressJob["verdict"]>,
  { text: string; className: string }
> = {
  passed: { text: "No failures found", className: "bg-add-bg text-add-fg" },
  new_failure: {
    text: "Fails after this PR (passed before)",
    className: "bg-del-bg text-del-fg",
  },
  existing_failure: {
    text: "Fails, but it already failed before this PR",
    className: "bg-hunk-bg text-muted",
  },
  failure: { text: "Fails (new code)", className: "bg-del-bg text-del-fg" },
};

interface Props {
  path: string;
  tier: Tier;
  start: (path: string, tier: Tier) => Promise<StressJob>;
  jobIdFor: (path: string) => string | undefined;
}

export function StressPanel({ path, tier, start, jobIdFor }: Props) {
  const { job, setJob, error, setError, isRunning } = useJob(
    api.getStress,
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

  const verdict = job?.verdict ? VERDICT[job.verdict] : null;
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={run}
          disabled={isRunning}
          className="rounded-md border border-border px-2 py-0.5 text-xs font-medium hover:bg-selected disabled:opacity-50"
        >
          {job && !isRunning ? "Stress-test again" : "🧪 Stress-test change"}
        </button>
        {job && isRunning && (
          <span className="text-xs text-muted">{STEP_LABEL[job.status]}</span>
        )}
        {verdict && (
          <span className={`rounded px-1.5 text-xs ${verdict.className}`}>
            {verdict.text}
          </span>
        )}
      </div>
      <ErrorNote error={error} />
      {job?.message && (
        <p className={job.status === "failed" ? "text-del-fg" : "text-muted"}>
          {job.status === "skipped" ? "Not tested: " : ""}
          <span className="whitespace-pre-wrap">{job.message}</span>
        </p>
      )}
      {job?.head && (
        <RunOutput
          label="After this PR"
          run={job.head}
          open={!job.head.passed}
        />
      )}
      {job?.base && (
        <RunOutput label="Before this PR" run={job.base} open={false} />
      )}
      {job?.test_code && (
        <details>
          <summary className="cursor-pointer text-xs text-muted">
            Generated tests
          </summary>
          <pre className="mt-1 max-h-96 overflow-auto rounded bg-panel p-2 font-mono text-xs">
            {job.test_code}
          </pre>
        </details>
      )}
    </div>
  );
}

function RunOutput({
  label,
  run,
  open,
}: {
  label: string;
  run: StressJob["head"];
  open: boolean;
}) {
  if (!run) return null;
  return (
    <details open={open}>
      <summary className="cursor-pointer text-xs text-muted">
        {label}:{" "}
        {run.passed ? "passed" : run.timed_out ? "timed out" : "failed"}
      </summary>
      <pre className="mt-1 max-h-96 overflow-auto rounded bg-panel p-2 font-mono text-xs whitespace-pre-wrap">
        {run.output}
      </pre>
    </details>
  );
}

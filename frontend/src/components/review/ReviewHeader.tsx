import type { ReviewSummary } from "@/lib/types";

interface Props {
  summary: ReviewSummary;
  reviewedFiles: number;
  totalFiles: number;
  reviewedLines: number;
  totalLines: number;
}

export function ReviewHeader({
  summary,
  reviewedFiles,
  totalFiles,
  reviewedLines,
  totalLines,
}: Props) {
  const { pull, stats, truncated } = summary;
  const pct = totalLines ? Math.round((reviewedLines / totalLines) * 100) : 100;
  const state = pull.merged ? "Merged" : pull.draft ? "Draft" : pull.state === "open" ? "Open" : "Closed";

  return (
    <header className="space-y-2 border-b border-border px-4 py-3">
      <div className="flex items-baseline gap-3">
        <h1 className="truncate text-lg font-semibold">
          {pull.title} <span className="font-normal text-muted">#{pull.number}</span>
        </h1>
        <a
          href={pull.html_url}
          target="_blank"
          rel="noreferrer"
          className="ml-auto shrink-0 text-sm text-accent hover:underline"
        >
          Open on GitHub ↗
        </a>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
        <span className="rounded-full border border-border px-2 text-xs">{state}</span>
        <span className="font-mono text-xs">
          {pull.base_ref} ← {pull.head_ref}
        </span>
        {pull.author && <span>by {pull.author.login}</span>}
        <span>
          {stats.files} files <span className="text-add-fg">+{stats.additions}</span>{" "}
          <span className="text-del-fg">−{stats.deletions}</span>
        </span>
        {stats.noise_files > 0 && (
          <span>
            {stats.noise_files} lockfile/generated ({stats.noise_lines} lines) set aside
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          <span>
            {reviewedFiles}/{totalFiles} files · {pct}% of lines
          </span>
          <div className="h-2 w-40 overflow-hidden rounded-full bg-panel">
            <div className="h-full bg-add-fg transition-all" style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>
      {truncated && (
        <p className="text-sm text-del-fg">
          GitHub only lists the first 3,000 files of a pull request; {pull.changed_files - stats.files}{" "}
          more aren&apos;t shown.
        </p>
      )}
    </header>
  );
}

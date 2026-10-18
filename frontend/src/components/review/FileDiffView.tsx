"use client";

import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api";
import type {
  CommentThread,
  DiffLine,
  DiffSide,
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

import { CommentComposer } from "./CommentComposer";
import { CommentThreadView } from "./CommentThreadView";
import { FileSummaryPanel } from "./FileSummaryPanel";
import { type RenderComments, RenderPanel } from "./RenderPanel";
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

export interface Anchor {
  side: DiffSide;
  line: number;
}

const anchorKey = (a: Anchor) => `${a.side}:${a.line}`;

/** Where a new comment on this diff line attaches (GitHub's side/line model). */
const anchorOf = (line: DiffLine): Anchor | null =>
  line.kind === "del" && line.old_number != null
    ? { side: "LEFT", line: line.old_number }
    : line.new_number != null
      ? { side: "RIGHT", line: line.new_number }
      : null;

interface Comments {
  threads: CommentThread[];
  onAdd: (path: string, anchor: Anchor, body: string) => Promise<unknown>;
  onReply: (thread: CommentThread, body: string) => Promise<unknown>;
}

interface Props {
  file: ReviewFile;
  comments: Comments;
  viewed: boolean;
  onToggleViewed: () => void;
  loadDiff: (path: string) => Promise<FileDiff>;
  llm: LLMStatus | null;
  summarize: (path: string, tier: Tier) => Promise<FileSummary>;
  cachedSummary: (path: string, tier: Tier) => Promise<FileSummary> | undefined;
  renderEnabled: boolean;
  startRender: (path: string, tier: Tier) => Promise<RenderJob>;
  renderJobFor: (path: string) => string | undefined;
  renderComments: RenderComments;
  stressEnabled: boolean;
  startStress: (path: string, tier: Tier) => Promise<StressJob>;
  stressJobFor: (path: string) => string | undefined;
}

export function FileDiffView({
  file,
  comments,
  viewed,
  onToggleViewed,
  loadDiff,
  llm,
  summarize,
  cachedSummary,
  renderEnabled,
  startRender,
  renderJobFor,
  renderComments,
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
          Viewed
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
              comments={renderComments}
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
      {diff && <DiffBody diff={diff} path={file.path} comments={comments} />}
    </article>
  );
}

function DiffBody({
  diff,
  path,
  comments,
}: {
  diff: FileDiff;
  path: string;
  comments: Comments;
}) {
  const [composing, setComposing] = useState<Anchor | null>(null);

  // Threads attach to the diff line they point at; the rest (outdated, or on lines the
  // diff doesn't show) are listed above the diff.
  const shown = new Set(
    diff.hunks.flatMap((h) =>
      h.lines.flatMap((l) => [
        l.new_number != null ? `RIGHT:${l.new_number}` : null,
        l.old_number != null ? `LEFT:${l.old_number}` : null,
      ]),
    ),
  );
  const byAnchor = new Map<string, CommentThread[]>();
  const elsewhere: CommentThread[] = [];
  for (const t of comments.threads) {
    const key = t.line != null && t.side ? `${t.side}:${t.line}` : null;
    if (key && shown.has(key))
      byAnchor.set(key, [...(byAnchor.get(key) ?? []), t]);
    else elsewhere.push(t);
  }

  const context: LineContext = {
    byAnchor,
    composing,
    setComposing,
    onAdd: (anchor, body) =>
      comments.onAdd(path, anchor, body).then(() => setComposing(null)),
    onReply: comments.onReply,
  };
  return (
    <>
      {elsewhere.length > 0 && (
        <details className="border-b border-border bg-panel py-1 text-sm">
          <summary className="cursor-pointer px-4 text-muted">
            {elsewhere.length} comment{elsewhere.length > 1 ? "s" : ""} on
            earlier versions or unchanged lines
          </summary>
          {elsewhere.map((t) => (
            <CommentThreadView
              key={t.id}
              thread={t}
              onReply={comments.onReply}
            />
          ))}
        </details>
      )}
      <div className="font-mono text-xs leading-5">
        {diff.hunks.map((hunk, i) => (
          <HunkView key={i} hunk={hunk} context={context} />
        ))}
      </div>
    </>
  );
}

interface LineContext {
  byAnchor: Map<string, CommentThread[]>;
  composing: Anchor | null;
  setComposing: (anchor: Anchor | null) => void;
  onAdd: (anchor: Anchor, body: string) => Promise<unknown>;
  onReply: (thread: CommentThread, body: string) => Promise<unknown>;
}

function HunkView({ hunk, context }: { hunk: Hunk; context: LineContext }) {
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
        hunk.lines.map((line, i) => (
          <LineRow key={i} line={line} context={context} />
        ))}
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

function LineRow({ line, context }: { line: DiffLine; context: LineContext }) {
  const style = ROW_STYLE[line.kind];
  const anchor = anchorOf(line);
  const threads = [
    ...(line.new_number != null
      ? (context.byAnchor.get(`RIGHT:${line.new_number}`) ?? [])
      : []),
    ...(line.old_number != null
      ? (context.byAnchor.get(`LEFT:${line.old_number}`) ?? [])
      : []),
  ];
  const composingHere =
    anchor &&
    context.composing &&
    anchorKey(anchor) === anchorKey(context.composing);
  return (
    <>
      <LineContent
        line={line}
        style={style}
        onComment={anchor ? () => context.setComposing(anchor) : undefined}
      />
      {threads.map((t) => (
        <CommentThreadView key={t.id} thread={t} onReply={context.onReply} />
      ))}
      {composingHere && (
        <div className="mx-4 my-2 rounded-md border border-border bg-panel p-3">
          <CommentComposer
            onSubmit={(body) => context.onAdd(anchor, body)}
            onCancel={() => context.setComposing(null)}
          />
        </div>
      )}
    </>
  );
}

function LineContent({
  line,
  style,
  onComment,
}: {
  line: DiffLine;
  style: (typeof ROW_STYLE)[DiffLine["kind"]];
  onComment?: () => void;
}) {
  return (
    <div
      className={`group relative grid grid-cols-[3.5rem_3.5rem_1fr] ${style.row}`}
    >
      {onComment && (
        <button
          type="button"
          onClick={onComment}
          title="Comment on this line"
          aria-label="Comment on this line"
          className="absolute top-0 left-0.5 hidden h-5 w-5 items-center justify-center rounded bg-accent text-white group-hover:flex"
        >
          +
        </button>
      )}
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

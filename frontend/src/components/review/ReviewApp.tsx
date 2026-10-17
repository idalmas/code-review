"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { buildTree, flattenTree } from "@/lib/fileTree";
import type { FileDiff, FileSummary, LLMStatus, ReviewSummary, Tier } from "@/lib/types";
import { useMe } from "@/lib/useMe";
import { useViewedFiles } from "@/lib/useViewedFiles";

import { SignInButton } from "../SignInButton";

import { FileDiffView } from "./FileDiffView";
import { FileTree } from "./FileTree";
import { ReviewHeader } from "./ReviewHeader";

interface Props {
  owner: string;
  repo: string;
  number: number;
}

export function ReviewApp({ owner, repo, number }: Props) {
  const [summary, setSummary] = useState<ReviewSummary | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const me = useMe();
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [hideNoise, setHideNoise] = useState(true);
  const [hideViewed, setHideViewed] = useState(false);
  const filterRef = useRef<HTMLInputElement>(null);
  const diffCache = useRef(new Map<string, Promise<FileDiff>>());
  const summaryCache = useRef(new Map<string, Promise<FileSummary>>());
  const [llm, setLlm] = useState<LLMStatus | null>(null);

  useEffect(() => {
    api.llmStatus().then(setLlm, () => setLlm(null));
  }, []);

  const { isViewed, setFileViewed } = useViewedFiles(`viewed:${owner}/${repo}#${number}`);

  useEffect(() => {
    let cancelled = false;
    api.getReview(owner, repo, number).then(
      (data) => !cancelled && setSummary(data),
      (err) => !cancelled && setError(err instanceof Error ? err : new Error(String(err))),
    );
    return () => {
      cancelled = true;
    };
  }, [owner, repo, number]);

  const loadDiff = useCallback(
    (path: string) => {
      let pending = diffCache.current.get(path);
      if (!pending) {
        pending = api.getFileDiff(owner, repo, number, path);
        pending.catch(() => diffCache.current.delete(path));
        diffCache.current.set(path, pending);
      }
      return pending;
    },
    [owner, repo, number],
  );

  const cachedSummary = useCallback(
    (path: string, tier: Tier) => summaryCache.current.get(`${tier}:${path}`),
    [],
  );

  // Each click asks again (and spends again); the latest answer is what we remember.
  const summarize = useCallback(
    (path: string, tier: Tier) => {
      const pending = api.summarizeFile(owner, repo, number, path, tier);
      summaryCache.current.set(`${tier}:${path}`, pending);
      pending.catch(() => summaryCache.current.delete(`${tier}:${path}`));
      return pending;
    },
    [owner, repo, number],
  );

  const visibleFiles = useMemo(() => {
    if (!summary) return [];
    const q = query.trim().toLowerCase();
    return summary.files.filter(
      (f) =>
        (!hideNoise || !f.is_noise) &&
        (!hideViewed || !isViewed(f) || f.path === selectedPath) &&
        (!q || f.path.toLowerCase().includes(q)),
    );
  }, [summary, query, hideNoise, hideViewed, isViewed, selectedPath]);

  const tree = useMemo(() => buildTree(visibleFiles), [visibleFiles]);
  const order = useMemo(() => flattenTree(tree), [tree]);
  const selected = summary?.files.find((f) => f.path === selectedPath) ?? null;

  const select = useCallback((path: string) => {
    setSelectedPath(path);
    history.replaceState(null, "", `#${encodeURIComponent(path)}`);
  }, []);

  // Restore the file from the URL hash, otherwise start at the first unviewed file.
  useEffect(() => {
    if (!summary || selectedPath) return;
    const fromHash = decodeURIComponent(location.hash.slice(1));
    const start =
      summary.files.find((f) => f.path === fromHash) ??
      order.find((f) => !isViewed(f)) ??
      order[0];
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time initial selection
    if (start) setSelectedPath(start.path);
  }, [summary, selectedPath, order, isViewed]);

  // Warm the cache for the next file so j feels instant.
  useEffect(() => {
    const i = order.findIndex((f) => f.path === selectedPath);
    const next = order[i + 1];
    if (next?.has_diff) loadDiff(next.path).catch(() => {});
  }, [order, selectedPath, loadDiff]);

  const move = useCallback(
    (delta: number) => {
      if (!order.length) return;
      const i = order.findIndex((f) => f.path === selectedPath);
      const next = order[Math.min(Math.max(i + delta, 0), order.length - 1)];
      if (next) select(next.path);
    },
    [order, selectedPath, select],
  );

  const toggleViewed = useCallback(() => {
    if (!selected) return;
    const nowViewed = !isViewed(selected);
    setFileViewed(selected, nowViewed);
    if (nowViewed) {
      const i = order.findIndex((f) => f.path === selected.path);
      const next = [...order.slice(i + 1), ...order.slice(0, i)].find((f) => !isViewed(f));
      if (next) select(next.path);
    }
  }, [selected, isViewed, setFileViewed, order, select]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      if (target.closest("input, textarea, [contenteditable]") || e.metaKey || e.ctrlKey) return;
      if (e.key === "j") move(1);
      else if (e.key === "k") move(-1);
      else if (e.key === "v") toggleViewed();
      else if (e.key === "/") {
        e.preventDefault();
        filterRef.current?.focus();
      } else return;
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move, toggleViewed]);

  if (error) {
    const signInMightHelp =
      error instanceof ApiError &&
      ["not_found", "unauthorized", "rate_limited"].includes(error.code) &&
      me?.login_enabled &&
      !me.user;
    return (
      <div className="mx-auto max-w-xl space-y-3 p-8">
        <h1 className="text-lg font-semibold">Couldn&apos;t load this pull request</h1>
        <p className="text-muted">{error.message}</p>
        {signInMightHelp && <SignInButton />}
      </div>
    );
  }
  if (!summary) return <p className="p-6 text-muted">Loading pull request…</p>;

  const reviewable = summary.files.filter((f) => !f.is_noise);
  const reviewedLines = reviewable
    .filter(isViewed)
    .reduce((n, f) => n + f.additions + f.deletions, 0);
  const totalLines = reviewable.reduce((n, f) => n + f.additions + f.deletions, 0);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <ReviewHeader
        summary={summary}
        reviewedFiles={reviewable.filter(isViewed).length}
        totalFiles={reviewable.length}
        reviewedLines={reviewedLines}
        totalLines={totalLines}
      />
      <div className="flex min-h-0 flex-1">
        <aside className="flex w-80 shrink-0 flex-col border-r border-border bg-panel">
          <div className="space-y-2 border-b border-border p-2">
            <input
              ref={filterRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Escape" && e.currentTarget.blur()}
              placeholder="Filter files  ( / )"
              className="w-full rounded-md border border-border bg-bg px-2 py-1 text-sm outline-none focus:border-accent"
            />
            <label className="flex items-center gap-2 text-xs text-muted">
              <input
                type="checkbox"
                checked={hideNoise}
                onChange={(e) => setHideNoise(e.target.checked)}
              />
              Hide lockfiles &amp; generated ({summary.stats.noise_files})
            </label>
            <label className="flex items-center gap-2 text-xs text-muted">
              <input
                type="checkbox"
                checked={hideViewed}
                onChange={(e) => setHideViewed(e.target.checked)}
              />
              Hide viewed
            </label>
          </div>
          <FileTree
            nodes={tree}
            selectedPath={selectedPath}
            isViewed={isViewed}
            onSelect={select}
          />
          <p className="border-t border-border p-2 text-xs text-muted">
            <kbd>j</kbd>/<kbd>k</kbd> next/prev · <kbd>v</kbd> mark viewed · <kbd>/</kbd> filter
          </p>
        </aside>
        <main className="min-w-0 flex-1 overflow-auto">
          {selected ? (
            <FileDiffView
              key={selected.path}
              file={selected}
              viewed={isViewed(selected)}
              onToggleViewed={toggleViewed}
              loadDiff={loadDiff}
              llm={llm}
              summarize={summarize}
              cachedSummary={cachedSummary}
            />
          ) : (
            <p className="p-6 text-muted">No files match the current filters.</p>
          )}
        </main>
      </div>
    </div>
  );
}

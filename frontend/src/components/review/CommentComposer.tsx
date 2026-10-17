"use client";

import { useState } from "react";

import { ErrorNote } from "./FileSummaryPanel";

interface Props {
  placeholder?: string;
  submitLabel?: string;
  /** Text to start with, e.g. context added by a render click. */
  initial?: string;
  onSubmit: (body: string) => Promise<unknown>;
  onCancel?: () => void;
}

export function CommentComposer({
  placeholder = "Leave a comment",
  submitLabel = "Comment",
  initial = "",
  onSubmit,
  onCancel,
}: Props) {
  const [body, setBody] = useState(initial);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  async function submit() {
    if (!body.trim() || pending) return;
    setPending(true);
    setError(null);
    try {
      await onSubmit(body);
      setBody("");
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-2 font-sans text-sm">
      <textarea
        autoFocus
        value={body}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
          if (e.key === "Escape") onCancel?.();
        }}
        placeholder={placeholder}
        rows={3}
        className="w-full rounded-md border border-border bg-bg p-2 outline-none focus:border-accent"
      />
      <ErrorNote error={error} />
      <div className="flex items-center justify-end gap-2">
        <span className="mr-auto text-xs text-muted">
          Posts to GitHub as you · ⌘/Ctrl+Enter
        </span>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="px-2 py-1 text-muted hover:text-fg"
          >
            Cancel
          </button>
        )}
        <button
          type="button"
          onClick={submit}
          disabled={pending || !body.trim()}
          className="rounded-md bg-accent px-3 py-1 font-medium text-white disabled:opacity-50"
        >
          {pending ? "Posting…" : submitLabel}
        </button>
      </div>
    </div>
  );
}

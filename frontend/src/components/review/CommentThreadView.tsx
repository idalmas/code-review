"use client";

import { useState } from "react";

import type { CommentThread, ReviewComment } from "@/lib/types";

import { Markdown } from "../Markdown";
import { CommentComposer } from "./CommentComposer";

interface Props {
  thread: CommentThread;
  onReply: (thread: CommentThread, body: string) => Promise<unknown>;
}

export function CommentThreadView({ thread, onReply }: Props) {
  const [replying, setReplying] = useState(false);
  return (
    <div className="mx-4 my-2 overflow-hidden rounded-md border border-border bg-bg font-sans text-sm">
      {thread.comments.map((c) => (
        <CommentView key={c.id} comment={c} />
      ))}
      <div className="border-t border-border bg-panel px-3 py-2">
        {replying ? (
          <CommentComposer
            placeholder="Reply"
            submitLabel="Reply"
            onSubmit={async (body) => {
              await onReply(thread, body);
              setReplying(false);
            }}
            onCancel={() => setReplying(false)}
          />
        ) : (
          <button
            type="button"
            onClick={() => setReplying(true)}
            className="w-full rounded-md border border-border bg-bg px-2 py-1 text-left text-muted hover:border-accent"
          >
            Reply…
          </button>
        )}
      </div>
    </div>
  );
}

function CommentView({ comment }: { comment: ReviewComment }) {
  const author = comment.author;
  const isBot = author?.is_bot || author?.login.endsWith("[bot]");
  return (
    <article className="space-y-1 border-b border-border px-3 py-2 last:border-b-0">
      <header className="flex items-center gap-2 text-xs">
        {author?.avatar_url && (
          // eslint-disable-next-line @next/next/no-img-element -- avatar from GitHub's CDN
          <img
            src={author.avatar_url}
            alt=""
            width={20}
            height={20}
            className="rounded-full"
          />
        )}
        <span className="font-semibold">
          {author?.login.replace(/\[bot\]$/, "") ?? "ghost"}
        </span>
        {isBot && (
          <span className="rounded-full border border-border px-1.5 text-muted">
            bot
          </span>
        )}
        <time
          className="text-muted"
          dateTime={comment.created_at}
          title={comment.created_at}
        >
          {timeAgo(comment.created_at)}
        </time>
        <a
          href={comment.html_url}
          target="_blank"
          rel="noreferrer"
          className="ml-auto text-muted hover:text-accent"
        >
          GitHub ↗
        </a>
      </header>
      <Markdown>{comment.body}</Markdown>
    </article>
  );
}

function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  for (const [unit, size] of [
    ["y", 31_536_000],
    ["mo", 2_592_000],
    ["d", 86_400],
    ["h", 3_600],
    ["m", 60],
  ] as const) {
    if (seconds >= size) return `${Math.floor(seconds / size)}${unit} ago`;
  }
  return "just now";
}

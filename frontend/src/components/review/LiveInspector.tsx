"use client";

import { useEffect, useRef, useState } from "react";

import type { RenderState } from "@/lib/types";

import { CommentComposer } from "./CommentComposer";

/** Where a click on the render lands in the diff. */
export interface PickTarget {
  path: string;
  line: number;
  /** False when the clicked code isn't changed, so we fell back to the nearest changed line. */
  exact: boolean;
  /** The clicked element's own source, e.g. "web/src/Avatar.tsx:3". */
  source: string;
}

interface Pick {
  chain: string[];
  tag: string;
  text: string;
}

interface Props {
  livePath: string;
  index: number;
  state: RenderState;
  resolve: (chain: string[]) => Promise<PickTarget | null>;
  comment: (target: PickTarget, body: string) => Promise<unknown>;
  onJump: (path: string) => void;
}

const isPick = (data: unknown): data is Pick & { type: "orbiter:pick" } => {
  const d = data as Record<string, unknown> | null;
  return (
    d?.type === "orbiter:pick" &&
    Array.isArray(d.chain) &&
    d.chain.length < 200 &&
    d.chain.every((s) => typeof s === "string" && /^[^\n]+:\d+$/.test(s)) &&
    typeof d.tag === "string" &&
    typeof d.text === "string"
  );
};

/**
 * The PR's own code, running live in a sandboxed iframe (opaque origin, no network; the
 * server adds the same restrictions as CSP). Click an element to comment on its source line.
 */
export function LiveInspector({
  livePath,
  index,
  state,
  resolve,
  comment,
  onJump,
}: Props) {
  const frame = useRef<HTMLIFrameElement>(null);
  const [pick, setPick] = useState<Pick | null>(null);
  const [target, setTarget] = useState<PickTarget | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [posted, setPosted] = useState<PickTarget | null>(null);

  useEffect(() => {
    async function onMessage(e: MessageEvent) {
      // Only trust messages from this exact frame, and only in the shape we expect.
      if (e.source !== frame.current?.contentWindow || !isPick(e.data)) return;
      const next = {
        chain: e.data.chain,
        tag: e.data.tag.slice(0, 20),
        text: e.data.text.slice(0, 60),
      };
      setPick(next);
      setPosted(null);
      const resolved = await resolve(next.chain);
      setTarget(resolved);
      setNotice(resolved ? null : "Not part of this PR's changes.");
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [resolve]);

  const { width, height } = state.viewport;
  const src = `/api/renders/${livePath}/index.html?state=${index}&inspect=1`;
  const context =
    pick &&
    `<sub>${state.name} render · \`<${pick.tag}>\`${pick.text ? ` “${pick.text}”` : ""}</sub>`;

  return (
    <div className="space-y-2 rounded-md border border-accent/40 p-2">
      <div className="max-h-[480px] overflow-auto rounded border border-border bg-white">
        <iframe
          ref={frame}
          src={src}
          title={`Live render: ${state.name}`}
          // allow-scripts without allow-same-origin: the frame gets an opaque origin, so it
          // can't read Orbiter's cookies or storage or call its API as the user.
          sandbox="allow-scripts"
          referrerPolicy="no-referrer"
          style={{
            width,
            height: Math.min(height, 480),
            border: 0,
            display: "block",
          }}
        />
      </div>
      {notice && <p className="text-xs text-del-fg">{notice}</p>}
      {pick && target && !posted && (
        <div className="space-y-2 rounded-md bg-panel p-2">
          <p className="text-xs">
            <button
              type="button"
              className="font-mono text-accent"
              onClick={() => onJump(target.path)}
            >
              {target.path}:{target.line}
            </button>
            {!target.exact && (
              <span
                className="text-muted"
                title={`Element from ${target.source}`}
              >
                {" "}
                · nearest changed line
              </span>
            )}
          </p>
          <CommentComposer
            key={`${target.path}:${target.line}:${pick.text}`}
            onSubmit={async (body) => {
              await comment(target, `${body.trim()}\n\n${context}`);
              setPosted(target);
            }}
            onCancel={() => setPick(null)}
          />
        </div>
      )}
      {posted && (
        <p className="text-xs text-add-fg">
          Posted on{" "}
          <button
            type="button"
            className="font-mono underline"
            onClick={() => onJump(posted.path)}
          >
            {posted.path}:{posted.line}
          </button>
        </p>
      )}
    </div>
  );
}

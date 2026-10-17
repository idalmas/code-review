"use client";

import { useState } from "react";

import type { TreeNode } from "@/lib/fileTree";
import type { ReviewFile } from "@/lib/types";

interface Props {
  nodes: TreeNode[];
  selectedPath: string | null;
  isViewed: (f: ReviewFile) => boolean;
  onSelect: (path: string) => void;
}

const STATUS_MARK: Record<string, { label: string; className: string }> = {
  added: { label: "A", className: "text-add-fg" },
  removed: { label: "D", className: "text-del-fg" },
  renamed: { label: "R", className: "text-accent" },
  copied: { label: "C", className: "text-accent" },
};

export function FileTree(props: Props) {
  return (
    <nav className="min-h-0 flex-1 overflow-auto py-1 text-sm">
      <TreeLevel {...props} depth={0} />
    </nav>
  );
}

function TreeLevel({ nodes, depth, ...rest }: Props & { depth: number }) {
  return nodes.map((node) =>
    node.kind === "dir" ? (
      <DirRow key={node.path} node={node} depth={depth} {...rest} />
    ) : (
      <FileRow key={node.file.path} node={node} depth={depth} {...rest} />
    ),
  );
}

function DirRow({
  node,
  depth,
  ...rest
}: Omit<Props, "nodes"> & {
  node: Extract<TreeNode, { kind: "dir" }>;
  depth: number;
}) {
  const [open, setOpen] = useState(true);
  return (
    <>
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-1 px-2 py-0.5 text-left text-muted hover:bg-selected"
        style={{ paddingLeft: 8 + depth * 12 }}
      >
        <span className="w-3 text-xs">{open ? "▾" : "▸"}</span>
        <span className="truncate">{node.name}</span>
      </button>
      {open && <TreeLevel nodes={node.children} depth={depth + 1} {...rest} />}
    </>
  );
}

function FileRow({
  node,
  depth,
  selectedPath,
  isViewed,
  onSelect,
}: Omit<Props, "nodes"> & {
  node: Extract<TreeNode, { kind: "file" }>;
  depth: number;
}) {
  const { file } = node;
  const selected = file.path === selectedPath;
  const viewed = isViewed(file);
  const mark = STATUS_MARK[file.status];

  return (
    <button
      ref={(el) => {
        if (selected) el?.scrollIntoView({ block: "nearest" });
      }}
      onClick={() => onSelect(file.path)}
      title={file.path}
      className={`flex w-full items-center gap-1 px-2 py-0.5 text-left hover:bg-selected ${
        selected ? "bg-selected font-medium" : ""
      } ${viewed ? "text-muted" : ""}`}
      style={{ paddingLeft: 8 + depth * 12 + 16 }}
    >
      <span
        className={`w-3 text-center text-xs ${viewed ? "text-add-fg" : "text-transparent"}`}
      >
        ✓
      </span>
      <span
        className={`truncate ${viewed ? "line-through decoration-muted/40" : ""}`}
      >
        {node.name}
      </span>
      {mark && (
        <span className={`text-xs ${mark.className}`}>{mark.label}</span>
      )}
      {file.is_noise && (
        <span className="text-xs text-muted">{file.category}</span>
      )}
      <span className="ml-auto shrink-0 font-mono text-xs">
        <span className="text-add-fg">+{file.additions}</span>{" "}
        <span className="text-del-fg">−{file.deletions}</span>
      </span>
    </button>
  );
}

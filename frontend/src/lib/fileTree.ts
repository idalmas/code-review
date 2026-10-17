import type { ReviewFile } from "./types";

export interface DirNode {
  kind: "dir";
  name: string;
  path: string;
  children: TreeNode[];
}

export interface FileNode {
  kind: "file";
  name: string;
  file: ReviewFile;
}

export type TreeNode = DirNode | FileNode;

/** Builds a tree and collapses single-child directory chains (`src/app/lib` → one row). */
export function buildTree(files: ReviewFile[]): TreeNode[] {
  const root: DirNode = { kind: "dir", name: "", path: "", children: [] };

  for (const file of files) {
    const parts = file.path.split("/");
    let dir = root;
    for (const part of parts.slice(0, -1)) {
      const path = dir.path ? `${dir.path}/${part}` : part;
      let next = dir.children.find(
        (c): c is DirNode => c.kind === "dir" && c.name === part,
      );
      if (!next) {
        next = { kind: "dir", name: part, path, children: [] };
        dir.children.push(next);
      }
      dir = next;
    }
    dir.children.push({ kind: "file", name: parts.at(-1)!, file });
  }

  return root.children.map(compact).sort(byDirThenName);
}

function compact(node: TreeNode): TreeNode {
  if (node.kind === "file") return node;
  let dir = node;
  while (dir.children.length === 1 && dir.children[0].kind === "dir") {
    const child: DirNode = dir.children[0];
    dir = { ...child, name: `${dir.name}/${child.name}` };
  }
  return { ...dir, children: dir.children.map(compact).sort(byDirThenName) };
}

function byDirThenName(a: TreeNode, b: TreeNode): number {
  if (a.kind !== b.kind) return a.kind === "dir" ? -1 : 1;
  return a.name.localeCompare(b.name, undefined, {
    numeric: true,
    sensitivity: "base",
  });
}

/** Files in the order they appear in the tree — what j/k should walk through. */
export function flattenTree(nodes: TreeNode[]): ReviewFile[] {
  return nodes.flatMap((n) =>
    n.kind === "file" ? [n.file] : flattenTree(n.children),
  );
}

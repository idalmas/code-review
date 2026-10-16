import type { FileDiff, ResolvedLink, ReviewSummary } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : res.statusText;
    throw new ApiError(detail || "Request failed", res.status, body.code ?? "unknown");
  }
  return res.json() as Promise<T>;
}

const prPath = (owner: string, repo: string, number: number) =>
  `/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/pulls/${number}`;

export const api = {
  resolveLink: (url: string) =>
    request<ResolvedLink>("/links/resolve", { method: "POST", body: JSON.stringify({ url }) }),

  getReview: (owner: string, repo: string, number: number) =>
    request<ReviewSummary>(`${prPath(owner, repo, number)}/review`),

  getFileDiff: (owner: string, repo: string, number: number, path: string) =>
    request<FileDiff>(
      `${prPath(owner, repo, number)}/files/${path.split("/").map(encodeURIComponent).join("/")}`,
    ),
};

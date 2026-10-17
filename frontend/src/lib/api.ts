import type {
  FileDiff,
  FileSummary,
  LLMStatus,
  Me,
  RenderJob,
  ResolvedLink,
  ReviewSummary,
  Tier,
} from "./types";

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
  if (res.status === 204) return undefined as T;
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : res.statusText;
    throw new ApiError(detail || "Request failed", res.status, body.code ?? "unknown");
  }
  return res.json() as Promise<T>;
}

const prPath = (owner: string, repo: string, number: number) =>
  `/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/pulls/${number}`;

/** Full-page navigation (not fetch): GitHub's consent screen can't be shown in a fetch. */
export const loginUrl = (returnTo: string) =>
  `/api/auth/login?return_to=${encodeURIComponent(returnTo)}`;

export const api = {
  me: () => request<Me>("/auth/me"),

  logout: () => request<void>("/auth/logout", { method: "POST" }),

  llmStatus: () => request<LLMStatus>("/llm"),

  renderAvailability: () => request<{ enabled: boolean }>("/renders"),

  startRender: (owner: string, repo: string, number: number, path: string, tier: Tier) =>
    request<RenderJob>(`${prPath(owner, repo, number)}/renders`, {
      method: "POST",
      body: JSON.stringify({ path, tier }),
    }),

  getRender: (id: string) => request<RenderJob>(`/renders/${encodeURIComponent(id)}`),

  summarizeFile: (owner: string, repo: string, number: number, path: string, tier: Tier) =>
    request<FileSummary>(`${prPath(owner, repo, number)}/summaries`, {
      method: "POST",
      body: JSON.stringify({ path, tier }),
    }),

  resolveLink: (url: string) =>
    request<ResolvedLink>("/links/resolve", { method: "POST", body: JSON.stringify({ url }) }),

  getReview: (owner: string, repo: string, number: number) =>
    request<ReviewSummary>(`${prPath(owner, repo, number)}/review`),

  getFileDiff: (owner: string, repo: string, number: number, path: string) =>
    request<FileDiff>(
      `${prPath(owner, repo, number)}/files/${path.split("/").map(encodeURIComponent).join("/")}`,
    ),
};

export const renderImageUrl = (id: string, version: "base" | "head", index: number) =>
  `/api/renders/${encodeURIComponent(id)}/${version}/${index}.png`;

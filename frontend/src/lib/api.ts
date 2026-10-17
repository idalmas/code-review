import type {
  CommentThread,
  DiffSide,
  FileDiff,
  FileSummary,
  LLMStatus,
  Me,
  RenderJob,
  ReviewComment,
  ResolvedLink,
  ReviewSummary,
  StressJob,
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
    const detail =
      typeof body.detail === "string" ? body.detail : res.statusText;
    throw new ApiError(
      detail || "Request failed",
      res.status,
      body.code ?? "unknown",
    );
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

  listComments: (owner: string, repo: string, number: number) =>
    request<CommentThread[]>(`${prPath(owner, repo, number)}/comments`),

  addComment: (
    owner: string,
    repo: string,
    number: number,
    comment: {
      path: string;
      line: number;
      side: DiffSide;
      body: string;
      start_line?: number;
    },
  ) =>
    request<CommentThread>(`${prPath(owner, repo, number)}/comments`, {
      method: "POST",
      body: JSON.stringify(comment),
    }),

  reply: (
    owner: string,
    repo: string,
    number: number,
    threadId: number,
    body: string,
  ) =>
    request<ReviewComment>(
      `${prPath(owner, repo, number)}/comments/${threadId}/replies`,
      {
        method: "POST",
        body: JSON.stringify({ body }),
      },
    ),

  renderAvailability: () => request<{ enabled: boolean }>("/renders"),

  startRender: (
    owner: string,
    repo: string,
    number: number,
    path: string,
    tier: Tier,
  ) =>
    request<RenderJob>(`${prPath(owner, repo, number)}/renders`, {
      method: "POST",
      body: JSON.stringify({ path, tier }),
    }),

  getRender: (id: string) =>
    request<RenderJob>(`/renders/${encodeURIComponent(id)}`),

  stressAvailability: () => request<{ enabled: boolean }>("/stress"),

  startStress: (
    owner: string,
    repo: string,
    number: number,
    path: string,
    tier: Tier,
  ) =>
    request<StressJob>(`${prPath(owner, repo, number)}/stress`, {
      method: "POST",
      body: JSON.stringify({ path, tier }),
    }),

  getStress: (id: string) =>
    request<StressJob>(`/stress/${encodeURIComponent(id)}`),

  summarizeFile: (
    owner: string,
    repo: string,
    number: number,
    path: string,
    tier: Tier,
  ) =>
    request<FileSummary>(`${prPath(owner, repo, number)}/summaries`, {
      method: "POST",
      body: JSON.stringify({ path, tier }),
    }),

  resolveLink: (url: string) =>
    request<ResolvedLink>("/links/resolve", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  getReview: (owner: string, repo: string, number: number) =>
    request<ReviewSummary>(`${prPath(owner, repo, number)}/review`),

  getFileDiff: (owner: string, repo: string, number: number, path: string) =>
    request<FileDiff>(
      `${prPath(owner, repo, number)}/files/${path.split("/").map(encodeURIComponent).join("/")}`,
    ),
};

export const renderImageUrl = (
  id: string,
  version: "base" | "head",
  index: number,
) => `/api/renders/${encodeURIComponent(id)}/${version}/${index}.png`;

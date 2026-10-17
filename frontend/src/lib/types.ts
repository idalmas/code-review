// Mirrors the FastAPI response models in backend/app/services/*/types.py.
// Browse them live at http://localhost:8000/docs.

export type FileStatus =
  | "added"
  | "removed"
  | "modified"
  | "renamed"
  | "copied"
  | "changed"
  | "unchanged";

export type FileCategory =
  | "source"
  | "test"
  | "docs"
  | "config"
  | "assets"
  | "lockfile"
  | "generated"
  | "vendored";

export interface ResolvedLink {
  owner: string;
  repo: string;
  number: number;
  app_path: string;
  github_url: string;
}

export interface GitHubUser {
  login: string;
  avatar_url: string | null;
  name: string | null;
}

export interface Me {
  login_enabled: boolean;
  user: GitHubUser | null;
}

export interface PullRequest {
  owner: string;
  repo: string;
  number: number;
  title: string;
  body: string | null;
  state: "open" | "closed";
  draft: boolean;
  merged: boolean;
  author: GitHubUser | null;
  base_ref: string;
  head_ref: string;
  base_sha: string;
  head_sha: string;
  html_url: string;
  additions: number;
  deletions: number;
  changed_files: number;
  commits: number;
  created_at: string;
  updated_at: string;
}

export interface ReviewFile {
  path: string;
  previous_path: string | null;
  status: FileStatus;
  additions: number;
  deletions: number;
  category: FileCategory;
  is_noise: boolean;
  has_diff: boolean;
  github_url: string;
}

export interface ReviewSummary {
  pull: PullRequest;
  files: ReviewFile[];
  stats: {
    files: number;
    additions: number;
    deletions: number;
    noise_files: number;
    noise_lines: number;
    by_category: Partial<Record<FileCategory, number>>;
  };
  truncated: boolean;
}

export interface DiffLine {
  kind: "context" | "add" | "del" | "meta";
  content: string;
  old_number: number | null;
  new_number: number | null;
}

export interface Hunk {
  header: string;
  old_start: number;
  old_lines: number;
  new_start: number;
  new_lines: number;
  section: string | null;
  lines: DiffLine[];
}

export interface FileDiff {
  file: ReviewFile;
  hunks: Hunk[];
  unavailable_reason: "binary_or_empty" | "too_large" | null;
}

export type Tier = "cheap" | "balanced" | "best";

export interface LLMStatus {
  enabled: boolean;
  provider: "anthropic" | "openai" | null;
  default_tier: Tier;
  tiers: { tier: Tier; label: string; description: string; model: string }[];
}

export interface FileSummary {
  path: string;
  text: string;
  tier: Tier;
  provider: "anthropic" | "openai";
  model: string;
  input_tokens: number;
  output_tokens: number;
  truncated: boolean;
}

export interface VersionShot {
  image: string;
  errors: string[];
  page_overflow: boolean;
  overflowing_elements: number;
  timed_out: boolean;
  ms: number;
}

export interface RenderState {
  name: string;
  viewport: { width: number; height: number };
  base: VersionShot | null;
  head: VersionShot | null;
  changed: boolean;
  problems: string[];
}

export interface RenderJob {
  id: string;
  path: string;
  tier: Tier;
  status:
    | "queued"
    | "downloading"
    | "writing_harness"
    | "installing"
    | "rendering"
    | "done"
    | "skipped"
    | "failed";
  message: string | null;
  states: RenderState[];
}

export interface TestRun {
  passed: boolean;
  timed_out: boolean;
  output: string;
}

export interface StressJob {
  id: string;
  path: string;
  tier: Tier;
  language: "python" | "javascript";
  status:
    | "queued"
    | "downloading"
    | "installing"
    | "writing_tests"
    | "running"
    | "done"
    | "skipped"
    | "failed";
  message: string | null;
  test_code: string | null;
  base: TestRun | null;
  head: TestRun | null;
  verdict: "passed" | "new_failure" | "existing_failure" | "failure" | null;
}

from typing import Literal

from pydantic import BaseModel

from app.services.diff import FileCategory, Hunk
from app.services.github import FileStatus, PullRequest


class FileNotInPullRequestError(LookupError):
    """Raised when asking for the diff of a path the PR didn't change."""


class ReviewFile(BaseModel):
    path: str
    previous_path: str | None
    status: FileStatus
    additions: int
    deletions: int
    category: FileCategory
    # Lockfiles, generated and vendored code: collapsed/hidden by default in the UI.
    is_noise: bool
    # False when GitHub didn't send a patch (binary files, or diffs too large to render).
    has_diff: bool
    github_url: str


class ReviewStats(BaseModel):
    files: int
    additions: int
    deletions: int
    noise_files: int
    noise_lines: int
    by_category: dict[str, int]


class ReviewSummary(BaseModel):
    pull: PullRequest
    files: list[ReviewFile]
    stats: ReviewStats
    # GitHub stops listing files after 3000; the rest only exist in the PR's raw diff.
    truncated: bool


DiffUnavailableReason = Literal["binary_or_empty", "too_large"]


class FileDiff(BaseModel):
    file: ReviewFile
    hunks: list[Hunk]
    unavailable_reason: DiffUnavailableReason | None = None

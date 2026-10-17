from typing import Literal

from pydantic import BaseModel

from app.services.diff import FileCategory, Hunk
from app.services.github import DiffSide, FileStatus, PullRequest, ReviewComment
from app.services.llm import Provider, Tier


class FileNotInPullRequestError(LookupError):
    """Raised when asking for the diff of a path the PR didn't change."""


class NothingToSummarizeError(ValueError):
    """The file has no text diff (binary, empty, or too large for GitHub to send)."""


class DiffTooLargeToSummarizeError(ValueError):
    """The diff is bigger than we're willing to send to a model in one request."""


class InvalidCommentError(ValueError):
    """The comment can't be posted as given (empty, too long, or not on a line in the diff)."""


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


class FileSummary(BaseModel):
    path: str
    text: str
    tier: Tier
    provider: Provider
    model: str
    input_tokens: int
    output_tokens: int
    truncated: bool


class CommentThread(BaseModel):
    """A comment on the diff plus its replies. `id` is the first comment's id."""

    id: int
    path: str
    line: int | None
    start_line: int | None
    side: DiffSide | None
    # The code it was attached to has changed since; GitHub no longer places it on a line.
    outdated: bool
    comments: list[ReviewComment]

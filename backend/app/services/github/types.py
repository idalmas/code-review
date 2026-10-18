from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class GitHubError(Exception):
    """Base error for anything that went wrong talking to GitHub."""

    status_code = 502
    code = "github_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(GitHubError):
    status_code = 404
    code = "not_found"


class AuthError(GitHubError):
    status_code = 401
    code = "unauthorized"


class RateLimitError(GitHubError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, message: str, reset_at: datetime | None = None) -> None:
        super().__init__(message)
        self.reset_at = reset_at


class GitHubUser(BaseModel):
    login: str
    avatar_url: str | None = None
    name: str | None = None
    # Apps such as Claude Code Review or Greptile post as bot users.
    is_bot: bool = False


class OAuthTokens(BaseModel):
    access_token: str
    # GitHub Apps issue expiring user tokens plus a single-use refresh token.
    # OAuth apps issue a non-expiring token and neither of these.
    refresh_token: str | None = None
    expires_at: datetime | None = None


class ValidationFailedError(GitHubError):
    """GitHub refused the write, e.g. a comment on a line that isn't part of the diff."""

    status_code = 422
    code = "github_validation_failed"


DiffSide = Literal["LEFT", "RIGHT"]


class ReviewComment(BaseModel):
    """A comment on a line of the PR's diff."""

    id: int
    path: str
    # Current position. None when the code it was on has since changed ("outdated").
    line: int | None
    start_line: int | None = None
    side: DiffSide | None = None
    original_line: int | None = None
    in_reply_to_id: int | None = None
    author: GitHubUser | None
    body: str
    created_at: datetime
    html_url: str


class OAuthExchangeError(GitHubError):
    """GitHub rejected an OAuth authorization code (expired, reused, or bad credentials)."""

    status_code = 400
    code = "oauth_exchange_failed"


class PullRequest(BaseModel):
    owner: str
    repo: str
    number: int
    title: str
    body: str | None
    state: Literal["open", "closed"]
    draft: bool
    merged: bool
    author: GitHubUser | None
    base_ref: str
    head_ref: str
    base_sha: str
    head_sha: str
    html_url: str
    additions: int
    deletions: int
    changed_files: int
    commits: int
    created_at: datetime
    updated_at: datetime


FileStatus = Literal["added", "removed", "modified", "renamed", "copied", "changed", "unchanged"]


class ChangedFile(BaseModel):
    filename: str
    previous_filename: str | None = None
    status: FileStatus
    additions: int
    deletions: int
    changes: int
    # GitHub omits the patch for binary files and for diffs it considers too large.
    patch: str | None = None

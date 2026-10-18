from pathlib import Path
from typing import Protocol

from .types import (
    AuthError,
    ChangedFile,
    DiffSide,
    FileStatus,
    GitHubError,
    GitHubUser,
    NotFoundError,
    OAuthExchangeError,
    OAuthTokens,
    PullRequest,
    RateLimitError,
    ReviewComment,
    ValidationFailedError,
)

__all__ = [
    "AuthError",
    "ChangedFile",
    "DiffSide",
    "FileStatus",
    "GitHubError",
    "GitHubService",
    "GitHubUser",
    "NotFoundError",
    "OAuthExchangeError",
    "OAuthTokens",
    "PullRequest",
    "RateLimitError",
    "ReviewComment",
    "ValidationFailedError",
    "MAX_FILES",
    "create_github_service",
]

# GitHub's "list pull request files" endpoint stops after this many files.
MAX_FILES = 3000


class GitHubService(Protocol):
    """Talks to GitHub on behalf of a user.

    Every read takes the viewer's OAuth `token` (None = anonymous, public repos only).
    Cached results are keyed per token, so one user never sees data fetched with another's.
    """

    async def get_pull_request(
        self, owner: str, repo: str, number: int, *, token: str | None
    ) -> PullRequest:
        """Fetch PR metadata. Raises a `GitHubError` subclass on failure."""
        ...

    async def list_files(
        self, owner: str, repo: str, number: int, *, token: str | None
    ) -> list[ChangedFile]:
        """Fetch every changed file (up to `MAX_FILES`), following pagination.

        Results are cached briefly, so calling this once per file view is cheap.
        """
        ...

    async def list_review_comments(
        self, owner: str, repo: str, number: int, *, token: str | None
    ) -> list[ReviewComment]:
        """Every comment on the PR's diff, oldest first. Never cached, so new comments
        (from people or review bots) show up on the next call."""
        ...

    async def create_review_comment(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        token: str,
        commit_id: str,
        path: str,
        line: int,
        side: DiffSide,
        body: str,
        start_line: int | None = None,
    ) -> ReviewComment:
        """Comment on `line` (or `start_line`..`line`) of `path` as the token's user.
        Raises `ValidationFailedError` if GitHub rejects the position."""
        ...

    async def reply_to_review_comment(
        self, owner: str, repo: str, number: int, comment_id: int, *, token: str, body: str
    ) -> ReviewComment:
        """Reply in the thread that `comment_id` belongs to."""
        ...

    async def download_tree(
        self, owner: str, repo: str, ref: str, *, token: str | None, dest: Path, max_bytes: int
    ) -> None:
        """Unpack the repository's files at `ref` into the new folder `dest`. Safe for
        untrusted repos: nothing is written outside `dest` (no `..`, absolute paths, devices
        or escaping links), and the download and unpacked size are capped at `max_bytes`.
        Raises `GitHubError`."""
        ...

    async def get_viewer(self, *, token: str) -> GitHubUser:
        """The user the token belongs to."""
        ...

    async def exchange_oauth_code(
        self, *, client_id: str, client_secret: str, code: str, redirect_uri: str
    ) -> OAuthTokens:
        """Trade an OAuth authorization code for the user's tokens.
        Raises `OAuthExchangeError` if GitHub rejects it."""
        ...

    async def refresh_oauth_token(
        self, *, client_id: str, client_secret: str, refresh_token: str
    ) -> OAuthTokens:
        """Swap a (single-use) refresh token for fresh tokens, for GitHub App user tokens.
        Raises `OAuthExchangeError` if it was revoked, expired or already used."""
        ...

    async def aclose(self) -> None:
        """Release network resources. Call on app shutdown."""
        ...


def create_github_service(
    *,
    api_url: str = "https://api.github.com",
    web_url: str = "https://github.com",
    cache_ttl_seconds: int = 120,
) -> GitHubService:
    """`api_url`/`web_url` point at GitHub Enterprise Server when self-hosting against it
    (e.g. `https://ghe.example.com/api/v3` and `https://ghe.example.com`)."""
    from .impl import GitHubServiceImpl

    return GitHubServiceImpl(api_url=api_url, web_url=web_url, cache_ttl_seconds=cache_ttl_seconds)

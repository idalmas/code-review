from pathlib import Path
from typing import Protocol

from .types import (
    AuthError,
    ChangedFile,
    FileStatus,
    GitHubError,
    GitHubUser,
    NotFoundError,
    OAuthExchangeError,
    PullRequest,
    RateLimitError,
)

__all__ = [
    "AuthError",
    "ChangedFile",
    "FileStatus",
    "GitHubError",
    "GitHubService",
    "GitHubUser",
    "NotFoundError",
    "OAuthExchangeError",
    "PullRequest",
    "RateLimitError",
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

    async def download_tarball(
        self, owner: str, repo: str, ref: str, *, token: str | None, dest: Path, max_bytes: int
    ) -> None:
        """Save the repository at `ref` as a .tar.gz at `dest`. Raises `GitHubError` if it
        fails or would exceed `max_bytes`."""
        ...

    async def get_viewer(self, *, token: str) -> GitHubUser:
        """The user the token belongs to."""
        ...

    async def exchange_oauth_code(
        self, *, client_id: str, client_secret: str, code: str, redirect_uri: str
    ) -> str:
        """Trade an OAuth authorization code for an access token.
        Raises `OAuthExchangeError` if GitHub rejects it."""
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

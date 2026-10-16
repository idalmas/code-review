from typing import Protocol

from .types import (
    AuthError,
    ChangedFile,
    FileStatus,
    GitHubError,
    GitHubUser,
    NotFoundError,
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
    "PullRequest",
    "RateLimitError",
    "MAX_FILES",
    "create_github_service",
]

# GitHub's "list pull request files" endpoint stops after this many files.
MAX_FILES = 3000


class GitHubService(Protocol):
    async def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequest:
        """Fetch PR metadata. Raises a `GitHubError` subclass on failure."""
        ...

    async def list_files(self, owner: str, repo: str, number: int) -> list[ChangedFile]:
        """Fetch every changed file (up to `MAX_FILES`), following pagination.

        Results are cached briefly, so calling this once per file view is cheap.
        """
        ...

    async def aclose(self) -> None:
        """Release network resources. Call on app shutdown."""
        ...


def create_github_service(
    *,
    token: str | None,
    api_url: str = "https://api.github.com",
    cache_ttl_seconds: int = 120,
) -> GitHubService:
    from .impl import GitHubServiceImpl

    return GitHubServiceImpl(token=token, api_url=api_url, cache_ttl_seconds=cache_ttl_seconds)

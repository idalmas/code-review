from typing import Protocol

from app.services.diff import DiffService
from app.services.github import GitHubService

from .types import (
    DiffUnavailableReason,
    FileDiff,
    FileNotInPullRequestError,
    ReviewFile,
    ReviewStats,
    ReviewSummary,
)

__all__ = [
    "DiffUnavailableReason",
    "FileDiff",
    "FileNotInPullRequestError",
    "ReviewFile",
    "ReviewService",
    "ReviewStats",
    "ReviewSummary",
    "create_review_service",
]


class ReviewService(Protocol):
    async def get_summary(self, owner: str, repo: str, number: int) -> ReviewSummary:
        """PR metadata plus every changed file (without hunks), classified and in
        tree order. Cheap enough to load up front even for thousands of files."""
        ...

    async def get_file_diff(self, owner: str, repo: str, number: int, path: str) -> FileDiff:
        """Parsed hunks for one file, so the UI can load large PRs lazily.
        Raises `FileNotInPullRequestError` if the PR didn't touch `path`."""
        ...


def create_review_service(*, github: GitHubService, diff: DiffService) -> ReviewService:
    from .impl import ReviewServiceImpl

    return ReviewServiceImpl(github=github, diff=diff)

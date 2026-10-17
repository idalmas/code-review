from typing import Protocol

from app.services.diff import DiffService
from app.services.github import GitHubService
from app.services.llm import LLMService, Tier

from .types import (
    DiffTooLargeToSummarizeError,
    DiffUnavailableReason,
    FileDiff,
    FileNotInPullRequestError,
    FileSummary,
    NothingToSummarizeError,
    ReviewFile,
    ReviewStats,
    ReviewSummary,
)

__all__ = [
    "MAX_SUMMARY_DIFF_CHARS",
    "DiffTooLargeToSummarizeError",
    "DiffUnavailableReason",
    "FileDiff",
    "FileNotInPullRequestError",
    "FileSummary",
    "NothingToSummarizeError",
    "ReviewFile",
    "ReviewService",
    "ReviewStats",
    "ReviewSummary",
    "create_review_service",
]


# Diffs longer than this are refused rather than silently truncated before summarizing.
MAX_SUMMARY_DIFF_CHARS = 200_000


class ReviewService(Protocol):
    async def get_summary(
        self, owner: str, repo: str, number: int, *, token: str | None
    ) -> ReviewSummary:
        """`token` is the viewer's GitHub token (None = anonymous, public repos only).

        PR metadata plus every changed file (without hunks), classified and in
        tree order. Cheap enough to load up front even for thousands of files."""
        ...

    async def get_file_diff(
        self, owner: str, repo: str, number: int, path: str, *, token: str | None
    ) -> FileDiff:
        """Parsed hunks for one file, so the UI can load large PRs lazily.
        Raises `FileNotInPullRequestError` if the PR didn't touch `path`."""
        ...

    async def summarize_file(
        self, owner: str, repo: str, number: int, path: str, *, tier: Tier, token: str | None
    ) -> FileSummary:
        """Plain-text explanation of one file's change and what a reviewer should check.
        Raises `NothingToSummarizeError`, `DiffTooLargeToSummarizeError`, plus anything
        `get_file_diff` or the LLM service raises."""
        ...


def create_review_service(
    *, github: GitHubService, diff: DiffService, llm: LLMService
) -> ReviewService:
    from .impl import ReviewServiceImpl

    return ReviewServiceImpl(github=github, diff=diff, llm=llm)

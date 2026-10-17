from typing import Protocol

from app.services.diff import DiffService
from app.services.github import DiffSide, GitHubService, ReviewComment
from app.services.llm import LLMService, Tier

from .types import (
    CommentThread,
    DiffTooLargeToSummarizeError,
    DiffUnavailableReason,
    FileDiff,
    FileNotInPullRequestError,
    FileSummary,
    InvalidCommentError,
    NothingToSummarizeError,
    ReviewFile,
    ReviewStats,
    ReviewSummary,
)

__all__ = [
    "MAX_COMMENT_CHARS",
    "MAX_SUMMARY_DIFF_CHARS",
    "CommentThread",
    "DiffTooLargeToSummarizeError",
    "DiffUnavailableReason",
    "FileDiff",
    "FileNotInPullRequestError",
    "FileSummary",
    "InvalidCommentError",
    "NothingToSummarizeError",
    "ReviewFile",
    "ReviewService",
    "ReviewStats",
    "ReviewSummary",
    "create_review_service",
]


# GitHub's own limit on a comment body.
MAX_COMMENT_CHARS = 65_536

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

    async def list_threads(
        self, owner: str, repo: str, number: int, *, token: str | None
    ) -> list[CommentThread]:
        """Every review thread on the diff (from people and review bots), oldest first."""
        ...

    async def add_comment(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        path: str,
        line: int,
        side: DiffSide,
        body: str,
        token: str,
        start_line: int | None = None,
    ) -> CommentThread:
        """Start a thread on a line of the diff, as the token's user, on the PR's latest
        commit. Raises `InvalidCommentError` if the line isn't in the diff."""
        ...

    async def reply(
        self, owner: str, repo: str, number: int, thread_id: int, *, body: str, token: str
    ) -> ReviewComment:
        """Add a reply to a thread. Raises `InvalidCommentError` for an empty body."""
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

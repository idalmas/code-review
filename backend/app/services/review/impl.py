import asyncio
import hashlib
from collections import Counter

from app.services.diff import DiffService
from app.services.github import MAX_FILES, ChangedFile, GitHubService, PullRequest

from .types import FileDiff, FileNotInPullRequestError, ReviewFile, ReviewStats, ReviewSummary


class ReviewServiceImpl:
    def __init__(self, *, github: GitHubService, diff: DiffService) -> None:
        self._github = github
        self._diff = diff

    async def get_summary(self, owner: str, repo: str, number: int) -> ReviewSummary:
        pull, changed = await asyncio.gather(
            self._github.get_pull_request(owner, repo, number),
            self._github.list_files(owner, repo, number),
        )
        files = sorted(
            (self._to_review_file(pull, f) for f in changed),
            key=lambda f: [part.lower() for part in f.path.split("/")],
        )
        return ReviewSummary(
            pull=pull,
            files=files,
            stats=_stats(files),
            truncated=len(changed) >= MAX_FILES and pull.changed_files > len(changed),
        )

    async def get_file_diff(self, owner: str, repo: str, number: int, path: str) -> FileDiff:
        pull, changed = await asyncio.gather(
            self._github.get_pull_request(owner, repo, number),
            self._github.list_files(owner, repo, number),
        )
        match = next((f for f in changed if f.filename == path), None)
        if match is None:
            raise FileNotInPullRequestError(f"{path} isn't part of this pull request.")

        file = self._to_review_file(pull, match)
        if match.patch is None:
            reason = "binary_or_empty" if match.changes == 0 else "too_large"
            return FileDiff(file=file, hunks=[], unavailable_reason=reason)
        return FileDiff(file=file, hunks=self._diff.parse_patch(match.patch))

    def _to_review_file(self, pull: PullRequest, f: ChangedFile) -> ReviewFile:
        category = self._diff.classify(f.filename)
        anchor = hashlib.sha256(f.filename.encode()).hexdigest()
        return ReviewFile(
            path=f.filename,
            previous_path=f.previous_filename,
            status=f.status,
            additions=f.additions,
            deletions=f.deletions,
            category=category,
            is_noise=self._diff.is_noise(category),
            has_diff=f.patch is not None,
            github_url=f"{pull.html_url}/files#diff-{anchor}",
        )


def _stats(files: list[ReviewFile]) -> ReviewStats:
    noise = [f for f in files if f.is_noise]
    return ReviewStats(
        files=len(files),
        additions=sum(f.additions for f in files),
        deletions=sum(f.deletions for f in files),
        noise_files=len(noise),
        noise_lines=sum(f.additions + f.deletions for f in noise),
        by_category=dict(Counter(f.category for f in files)),
    )

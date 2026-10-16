from typing import Protocol

from .types import InvalidLinkError, PullRequestRef, ResolvedLink

__all__ = [
    "InvalidLinkError",
    "LinkService",
    "PullRequestRef",
    "ResolvedLink",
    "create_link_service",
]


class LinkService(Protocol):
    def parse(self, raw: str) -> PullRequestRef:
        """Parse a GitHub PR URL or `owner/repo#123` shorthand.

        Accepts any PR sub-page (`/files`, `/commits`, ...), missing scheme, `www.`,
        query strings and fragments. Raises `InvalidLinkError` otherwise.
        """
        ...

    def resolve(self, raw: str) -> ResolvedLink:
        """Like `parse`, but returns the canonical GitHub URL and the path in this tool."""
        ...


def create_link_service() -> LinkService:
    from .impl import LinkServiceImpl

    return LinkServiceImpl()

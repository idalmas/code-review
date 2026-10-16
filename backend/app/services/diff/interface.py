from typing import Protocol

from .types import (
    NOISE_CATEGORIES,
    DiffLine,
    FileCategory,
    Hunk,
    LineKind,
    PatchParseError,
)

__all__ = [
    "NOISE_CATEGORIES",
    "DiffLine",
    "DiffService",
    "FileCategory",
    "Hunk",
    "LineKind",
    "PatchParseError",
    "create_diff_service",
]


class DiffService(Protocol):
    def parse_patch(self, patch: str) -> list[Hunk]:
        """Parse a unified diff body (starting at the first `@@`) into hunks with
        old/new line numbers. Raises `PatchParseError` on malformed input."""
        ...

    def classify(self, path: str) -> FileCategory:
        """Guess what kind of file this is from its path alone."""
        ...

    def is_noise(self, category: FileCategory) -> bool:
        """True for files reviewers usually skip (lockfiles, generated, vendored)."""
        ...


def create_diff_service() -> DiffService:
    from .impl import DiffServiceImpl

    return DiffServiceImpl()

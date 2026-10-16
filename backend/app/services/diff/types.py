from typing import Literal

from pydantic import BaseModel

LineKind = Literal["context", "add", "del", "meta"]

FileCategory = Literal[
    "source",
    "test",
    "docs",
    "config",
    "assets",
    "lockfile",
    "generated",
    "vendored",
]

# Categories that are usually safe to skim or skip in a large diff.
NOISE_CATEGORIES: frozenset[FileCategory] = frozenset({"lockfile", "generated", "vendored"})


class DiffLine(BaseModel):
    kind: LineKind
    content: str
    old_number: int | None = None
    new_number: int | None = None


class Hunk(BaseModel):
    header: str
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    # The function/class name GitHub prints after the second `@@`, if any.
    section: str | None = None
    lines: list[DiffLine]


class PatchParseError(ValueError):
    """Raised when a patch is not a valid unified diff."""

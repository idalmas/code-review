import re
from pathlib import PurePosixPath

from .types import NOISE_CATEGORIES, DiffLine, FileCategory, Hunk, PatchParseError

_HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_lines>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_lines>\d+))? @@ ?(?P<section>.*)$"
)

_LOCKFILES = {
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "bun.lock",
    "poetry.lock",
    "pipfile.lock",
    "uv.lock",
    "pdm.lock",
    "cargo.lock",
    "gemfile.lock",
    "composer.lock",
    "go.sum",
    "flake.lock",
    "podfile.lock",
    "package.resolved",
    "mix.lock",
    "pubspec.lock",
}
_VENDORED_DIRS = {"vendor", "node_modules", "third_party", "third-party", "bower_components"}
_GENERATED_DIRS = {"__generated__", "generated", "__snapshots__", "dist", "build", ".next"}
_GENERATED_SUFFIXES = (
    ".min.js",
    ".min.css",
    ".map",
    "_pb2.py",
    "_pb2.pyi",
    "_pb2_grpc.py",
    ".pb.go",
    ".pb.ts",
    ".g.dart",
    ".freezed.dart",
    ".designer.cs",
    ".snap",
)
_TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "e2e", "testdata", "fixtures"}
_TEST_NAME_RE = re.compile(
    r"(^test_.*\.py$|_test\.(py|go|rb|exs?)$|\.(test|spec)\.[cm]?[jt]sx?$|Test\.(java|kt|cs)$)"
)
_DOC_SUFFIXES = {".md", ".mdx", ".rst", ".adoc", ".txt"}
_DOC_DIRS = {"docs", "doc", "documentation"}
_ASSET_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".avif",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp4", ".mp3", ".pdf",
}  # fmt: skip
_CONFIG_SUFFIXES = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".lock", ".env"}
_CONFIG_NAMES = {"dockerfile", "makefile", "procfile", ".gitignore", ".dockerignore", ".npmrc"}


class DiffServiceImpl:
    def parse_patch(self, patch: str) -> list[Hunk]:
        hunks: list[Hunk] = []
        current: Hunk | None = None
        old_no = new_no = 0

        for raw in patch.split("\n"):
            if raw.startswith("@@"):
                match = _HUNK_HEADER_RE.match(raw)
                if match is None:
                    raise PatchParseError(f"Malformed hunk header: {raw!r}")
                old_no = int(match["old_start"])
                new_no = int(match["new_start"])
                current = Hunk(
                    header=raw,
                    old_start=old_no,
                    old_lines=int(match["old_lines"] or 1),
                    new_start=new_no,
                    new_lines=int(match["new_lines"] or 1),
                    section=match["section"].strip() or None,
                    lines=[],
                )
                hunks.append(current)
                continue

            if current is None:
                if raw == "":
                    continue
                raise PatchParseError("Patch content appears before the first hunk header.")

            marker, content = raw[:1], raw[1:]
            if marker == "+":
                current.lines.append(DiffLine(kind="add", content=content, new_number=new_no))
                new_no += 1
            elif marker == "-":
                current.lines.append(DiffLine(kind="del", content=content, old_number=old_no))
                old_no += 1
            elif marker == "\\":
                current.lines.append(DiffLine(kind="meta", content=raw[2:]))
            elif marker == " " or raw == "":
                # GitHub drops the trailing space on blank context lines at the end of a patch.
                if raw == "" and _hunk_complete(current, old_no, new_no):
                    continue
                current.lines.append(
                    DiffLine(kind="context", content=content, old_number=old_no, new_number=new_no)
                )
                old_no += 1
                new_no += 1
            else:
                raise PatchParseError(f"Unexpected diff line: {raw!r}")

        return hunks

    def classify(self, path: str) -> FileCategory:
        p = PurePosixPath(path)
        name = p.name.lower()
        dirs = {part.lower() for part in p.parts[:-1]}

        if dirs & _VENDORED_DIRS:
            return "vendored"
        if name in _LOCKFILES:
            return "lockfile"
        if dirs & _GENERATED_DIRS or name.endswith(_GENERATED_SUFFIXES) or ".generated." in name:
            return "generated"
        if dirs & _TEST_DIRS or _TEST_NAME_RE.search(p.name):
            return "test"
        suffix = p.suffix.lower()
        if suffix in _ASSET_SUFFIXES:
            return "assets"
        if (
            suffix in _DOC_SUFFIXES
            or (dirs & _DOC_DIRS)
            or name.startswith(("readme", "changelog"))
        ):
            return "docs"
        if (
            suffix in _CONFIG_SUFFIXES
            or name in _CONFIG_NAMES
            or name.startswith(".env")
            or ".github" in dirs
        ):
            return "config"
        return "source"

    def is_noise(self, category: FileCategory) -> bool:
        return category in NOISE_CATEGORIES


def _hunk_complete(hunk: Hunk, old_no: int, new_no: int) -> bool:
    return old_no >= hunk.old_start + hunk.old_lines and new_no >= hunk.new_start + hunk.new_lines

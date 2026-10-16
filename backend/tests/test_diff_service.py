import pytest

from app.services.diff import PatchParseError, create_diff_service

diff = create_diff_service()

PATCH = """@@ -1,4 +1,5 @@ def main():
 import os
-import sys
+import sys, re
+import json
 
 print("hi")
\\ No newline at end of file
@@ -20 +21 @@ class Foo:
-    x = 1
+    x = 2"""


def test_parse_patch_tracks_line_numbers() -> None:
    hunks = diff.parse_patch(PATCH)
    assert len(hunks) == 2

    first = hunks[0]
    assert first.section == "def main():"
    assert [(line.kind, line.old_number, line.new_number) for line in first.lines] == [
        ("context", 1, 1),
        ("del", 2, None),
        ("add", None, 2),
        ("add", None, 3),
        ("context", 3, 4),
        ("context", 4, 5),
        ("meta", None, None),
    ]

    second = hunks[1]
    assert (second.old_start, second.old_lines, second.new_start, second.new_lines) == (
        20,
        1,
        21,
        1,
    )
    assert [line.content for line in second.lines] == ["    x = 1", "    x = 2"]


def test_parse_patch_rejects_garbage() -> None:
    with pytest.raises(PatchParseError):
        diff.parse_patch("hello\n@@ -1 +1 @@\n x")
    with pytest.raises(PatchParseError):
        diff.parse_patch("@@ nope @@")


@pytest.mark.parametrize(
    ("path", "category"),
    [
        ("src/app/page.tsx", "source"),
        ("backend/app/main.py", "source"),
        ("package-lock.json", "lockfile"),
        ("frontend/pnpm-lock.yaml", "lockfile"),
        ("go.sum", "lockfile"),
        ("vendor/github.com/x/y.go", "vendored"),
        ("api/foo_pb2.py", "generated"),
        ("static/app.min.js", "generated"),
        ("src/__generated__/schema.ts", "generated"),
        ("tests/test_links.py", "test"),
        ("src/button.test.tsx", "test"),
        ("pkg/server_test.go", "test"),
        ("README.md", "docs"),
        ("docs/guide/setup.html", "docs"),
        ("public/logo.svg", "assets"),
        ("pyproject.toml", "config"),
        (".github/workflows/ci.yml", "config"),
        ("Dockerfile", "config"),
    ],
)
def test_classify(path: str, category: str) -> None:
    assert diff.classify(path) == category


def test_is_noise() -> None:
    assert diff.is_noise("lockfile")
    assert diff.is_noise("generated")
    assert not diff.is_noise("source")
    assert not diff.is_noise("test")

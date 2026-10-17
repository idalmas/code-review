import pytest

from app.services.diff import create_diff_service
from app.services.github import ChangedFile
from app.services.review import (
    MAX_SUMMARY_DIFF_CHARS,
    DiffTooLargeToSummarizeError,
    FileNotInPullRequestError,
    NothingToSummarizeError,
    create_review_service,
)

from .fakes import SAMPLE_FILES, FakeGitHubService, FakeLLMService, make_pull


@pytest.fixture
def llm():
    return FakeLLMService()


@pytest.fixture
def review(llm):
    github = FakeGitHubService(make_pull(changed_files=4), SAMPLE_FILES)
    return create_review_service(github=github, diff=create_diff_service(), llm=llm)


async def test_summary_sorts_classifies_and_counts(review) -> None:
    summary = await review.get_summary("acme", "api", 7, token=None)

    assert [f.path for f in summary.files] == [
        "logo.png",
        "package-lock.json",
        "src/A.py",
        "src/b.py",
    ]
    lock = summary.files[1]
    assert lock.category == "lockfile" and lock.is_noise and not lock.has_diff
    assert lock.github_url.startswith("https://github.com/acme/api/pull/7/files#diff-")

    assert summary.stats.files == 4
    assert summary.stats.additions == 503
    assert summary.stats.noise_files == 1
    assert summary.stats.noise_lines == 900
    assert summary.stats.by_category == {"assets": 1, "lockfile": 1, "source": 2}
    assert summary.truncated is False


async def test_file_diff_parses_hunks(review) -> None:
    diff = await review.get_file_diff("acme", "api", 7, "src/A.py", token=None)
    assert diff.unavailable_reason is None
    assert [line.content for line in diff.hunks[0].lines] == ["x", "y"]


async def test_file_diff_explains_missing_patches(review) -> None:
    assert (
        await review.get_file_diff("acme", "api", 7, "package-lock.json", token=None)
    ).unavailable_reason == ("too_large")
    assert (
        await review.get_file_diff("acme", "api", 7, "logo.png", token=None)
    ).unavailable_reason == ("binary_or_empty")


async def test_file_diff_unknown_path(review) -> None:
    with pytest.raises(FileNotInPullRequestError):
        await review.get_file_diff("acme", "api", 7, "nope.py", token=None)


async def test_summarize_file_sends_diff_as_untrusted_data(review, llm) -> None:
    summary = await review.summarize_file("acme", "api", 7, "src/A.py", tier="best", token=None)

    assert summary.text == "Adds two names."
    assert summary.model == "claude-haiku-5-5" and summary.input_tokens == 120
    request = llm.requests[0]
    assert request.tier == "best"
    assert "<diff>\n@@ -0,0 +1,2 @@\n+x\n+y\n</diff>" in request.prompt
    assert "File: src/A.py (added, +2 -0)" in request.prompt
    assert "untrusted" in request.system


async def test_summarize_refuses_files_without_text_diff(review, llm) -> None:
    for path in ("package-lock.json", "logo.png"):
        with pytest.raises(NothingToSummarizeError):
            await review.summarize_file("acme", "api", 7, path, tier="cheap", token=None)
    assert llm.requests == []


async def test_summarize_refuses_instead_of_truncating(llm) -> None:
    n = MAX_SUMMARY_DIFF_CHARS // 10
    huge = ChangedFile(filename="big.py", status="added", additions=n, deletions=0, changes=n,
                       patch=f"@@ -0,0 +1,{n} @@\n" + "\n".join(["+0123456789"] * n))  # fmt: skip
    github = FakeGitHubService(make_pull(), [huge])
    review = create_review_service(github=github, diff=create_diff_service(), llm=llm)
    with pytest.raises(DiffTooLargeToSummarizeError):
        await review.summarize_file("acme", "api", 7, "big.py", tier="cheap", token=None)
    assert llm.requests == []

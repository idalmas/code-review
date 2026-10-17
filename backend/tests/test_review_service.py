import pytest

from app.services.diff import create_diff_service
from app.services.review import FileNotInPullRequestError, create_review_service

from .fakes import SAMPLE_FILES, FakeGitHubService, make_pull


@pytest.fixture
def review():
    github = FakeGitHubService(make_pull(changed_files=4), SAMPLE_FILES)
    return create_review_service(github=github, diff=create_diff_service())


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

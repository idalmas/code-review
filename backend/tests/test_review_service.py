import pytest

from app.services.diff import create_diff_service
from app.services.github import ChangedFile
from app.services.review import (
    MAX_SUMMARY_DIFF_CHARS,
    DiffTooLargeToSummarizeError,
    FileNotInPullRequestError,
    InvalidCommentError,
    NothingToSummarizeError,
    create_review_service,
)

from .fakes import SAMPLE_FILES, FakeGitHubService, FakeLLMService, make_comment, make_pull


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


async def test_threads_group_replies_and_flag_outdated(review) -> None:
    github = review._github  # the fake behind the fixture
    github.comments = [
        make_comment(1, "src/A.py", 2, "Nit: rename", bot=True),
        make_comment(2, "src/A.py", 2, "Done", in_reply_to_id=1),
        make_comment(3, "src/b.py", None, "Old note"),
    ]
    threads = await review.list_threads("acme", "api", 7, token=None)
    assert [(t.id, len(t.comments), t.outdated) for t in threads] == [(1, 2, False), (3, 1, True)]
    assert threads[0].comments[0].author.is_bot


async def test_add_comment_only_on_diff_lines(review) -> None:
    github = review._github
    thread = await review.add_comment("acme", "api", 7, path="src/A.py", line=2, side="RIGHT",
                                      body="  Looks off  ", token="t")  # fmt: skip
    assert thread.comments[0].body == "Looks off"
    assert github.posted[0]["commit_id"] == "b" * 40  # latest commit of the PR
    assert github.posted[0]["token"] == "t"

    for line, side in ((9, "RIGHT"), (1, "LEFT")):  # not in the diff / no old lines (added file)
        with pytest.raises(InvalidCommentError):
            await review.add_comment("acme", "api", 7, path="src/A.py", line=line, side=side,
                                     body="x", token="t")  # fmt: skip
    with pytest.raises(InvalidCommentError):
        await review.add_comment("acme", "api", 7, path="src/A.py", line=2, side="RIGHT",
                                 body="   ", token="t")  # fmt: skip


async def test_reply(review) -> None:
    review._github.comments = [make_comment(1, "src/A.py", 2, "Why?")]
    reply = await review.reply("acme", "api", 7, 1, body="Because", token="t")
    assert reply.in_reply_to_id == 1
    threads = await review.list_threads("acme", "api", 7, token=None)
    assert [c.body for c in threads[0].comments] == ["Why?", "Because"]

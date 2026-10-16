import pytest

from app.services.links import InvalidLinkError, create_link_service

links = create_link_service()


@pytest.mark.parametrize(
    "raw",
    [
        "https://github.com/vercel/next.js/pull/123",
        "https://github.com/vercel/next.js/pull/123/files",
        "https://github.com/vercel/next.js/pull/123/files?diff=split#diff-abc",
        "github.com/vercel/next.js/pull/123",
        "www.github.com/vercel/next.js/pull/123/",
        "  http://github.com/vercel/next.js/pulls/123/commits  ",
        "vercel/next.js#123",
    ],
)
def test_parses_pull_request_links(raw: str) -> None:
    ref = links.parse(raw)
    assert (ref.owner, ref.repo, ref.number) == ("vercel", "next.js", 123)


def test_resolve_maps_to_app_path() -> None:
    resolved = links.resolve("https://github.com/acme/api/pull/7/files")
    assert resolved.app_path == "/acme/api/pull/7"
    assert resolved.github_url == "https://github.com/acme/api/pull/7"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "https://gitlab.com/acme/api/pull/7",
        "https://github.com/acme/api",
        "https://github.com/acme/api/issues/7",
        "https://github.com/acme/api/pull/0",
        "https://github.com.evil.example/acme/api/pull/7",
        "not a link",
    ],
)
def test_rejects_non_pull_request_input(raw: str) -> None:
    with pytest.raises(InvalidLinkError):
        links.parse(raw)

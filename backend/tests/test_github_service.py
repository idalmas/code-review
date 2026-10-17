import httpx
import pytest

from app.services.github import NotFoundError, OAuthExchangeError, RateLimitError
from app.services.github.impl import GitHubServiceImpl  # tests may reach into impl

PR_JSON = {
    "number": 7,
    "title": "Add things",
    "body": "desc",
    "state": "open",
    "draft": False,
    "merged": False,
    "user": {"login": "octo", "avatar_url": "https://x/a.png"},
    "base": {"ref": "main", "sha": "a" * 40},
    "head": {"ref": "feature", "sha": "b" * 40},
    "html_url": "https://github.com/acme/api/pull/7",
    "additions": 3,
    "deletions": 1,
    "changed_files": 150,
    "commits": 2,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-02T00:00:00Z",
}


def file_json(i: int) -> dict:
    return {"filename": f"f{i}.py", "status": "modified", "additions": 1, "deletions": 0,
            "changes": 1, "patch": "@@ -1 +1 @@\n+x"}  # fmt: skip


def make_service(handler) -> tuple[GitHubServiceImpl, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    service = GitHubServiceImpl(
        api_url="https://api.github.test", web_url="https://github.test", cache_ttl_seconds=60,
        transport=httpx.MockTransport(record),
    )  # fmt: skip
    return service, seen


async def test_get_pull_request_maps_fields_and_sends_token() -> None:
    service, seen = make_service(lambda r: httpx.Response(200, json=PR_JSON))
    pull = await service.get_pull_request("acme", "api", 7, token="t0k")

    assert pull.author.login == "octo"
    assert pull.base_ref == "main" and pull.head_sha == "b" * 40
    assert seen[0].headers["Authorization"] == "Bearer t0k"


async def test_list_files_paginates_and_caches() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        count = 100 if page == 1 else 50
        start = (page - 1) * 100
        return httpx.Response(200, json=[file_json(start + i) for i in range(count)])

    service, seen = make_service(handler)
    files = await service.list_files("acme", "api", 7, token="alice")
    assert len(files) == 150
    assert len(seen) == 2

    await service.list_files("acme", "api", 7, token="alice")
    assert len(seen) == 2  # served from cache

    # A different viewer must never be served another viewer's cached (maybe private) data.
    await service.list_files("acme", "api", 7, token="bob")
    assert len(seen) == 4
    assert seen[-1].headers["Authorization"] == "Bearer bob"
    await service.list_files("acme", "api", 7, token=None)
    assert len(seen) == 6
    assert "Authorization" not in seen[-1].headers


async def test_errors_are_mapped() -> None:
    service, _ = make_service(lambda r: httpx.Response(404, json={"message": "Not Found"}))
    with pytest.raises(NotFoundError):
        await service.get_pull_request("acme", "api", 7, token=None)

    limited = httpx.Response(
        403,
        json={"message": "API rate limit exceeded"},
        headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1800000000"},
    )
    service, _ = make_service(lambda r: limited)
    with pytest.raises(RateLimitError) as info:
        await service.get_pull_request("acme", "api", 7, token=None)
    assert info.value.reset_at is not None


async def test_exchange_oauth_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://github.test/login/oauth/access_token"
        if b"code=good" in request.content:
            return httpx.Response(200, json={"access_token": "gho_x", "token_type": "bearer"})
        return httpx.Response(200, json={"error": "bad_verification_code"})

    service, _ = make_service(handler)
    args = dict(client_id="id", client_secret="s", redirect_uri="http://app/cb")
    assert await service.exchange_oauth_code(code="good", **args) == "gho_x"
    with pytest.raises(OAuthExchangeError):
        await service.exchange_oauth_code(code="bad", **args)

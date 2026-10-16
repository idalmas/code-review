import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

import httpx

from .types import (
    AuthError,
    ChangedFile,
    GitHubError,
    GitHubUser,
    NotFoundError,
    PullRequest,
    RateLimitError,
)

_T = TypeVar("_T")

_PER_PAGE = 100
_MAX_PAGES = 30  # 30 * 100 = GitHub's 3000-file cap


class _TTLCache:
    """Tiny in-process cache that also collapses concurrent fetches of the same key."""

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._entries: dict[tuple, tuple[float, Any]] = {}
        self._inflight: dict[tuple, asyncio.Future] = {}

    async def get_or_fetch(self, key: tuple, fetch: Callable[[], Awaitable[_T]]) -> _T:
        hit = self._entries.get(key)
        if hit is not None and hit[0] > time.monotonic():
            return hit[1]
        if key in self._inflight:
            return await self._inflight[key]

        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._inflight[key] = future
        try:
            value = await fetch()
        except BaseException as exc:
            future.set_exception(exc)
            future.exception()  # mark retrieved so lone failures don't warn
            raise
        else:
            self._entries[key] = (time.monotonic() + self._ttl, value)
            future.set_result(value)
            return value
        finally:
            del self._inflight[key]


class GitHubServiceImpl:
    def __init__(
        self,
        *,
        token: str | None,
        api_url: str,
        cache_ttl_seconds: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "code-review-tool",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url=api_url, headers=headers, timeout=30.0, transport=transport
        )
        self._cache = _TTLCache(cache_ttl_seconds)

    async def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequest:
        async def fetch() -> PullRequest:
            data = await self._get_json(f"/repos/{owner}/{repo}/pulls/{number}")
            return _to_pull_request(owner, repo, data)

        return await self._cache.get_or_fetch(("pr", owner, repo, number), fetch)

    async def list_files(self, owner: str, repo: str, number: int) -> list[ChangedFile]:
        async def fetch() -> list[ChangedFile]:
            files: list[ChangedFile] = []
            for page in range(1, _MAX_PAGES + 1):
                batch = await self._get_json(
                    f"/repos/{owner}/{repo}/pulls/{number}/files",
                    params={"per_page": _PER_PAGE, "page": page},
                )
                files.extend(ChangedFile.model_validate(item) for item in batch)
                if len(batch) < _PER_PAGE:
                    break
            return files

        return await self._cache.get_or_fetch(("files", owner, repo, number), fetch)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get_json(self, path: str, params: dict | None = None) -> Any:
        try:
            response = await self._client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise GitHubError(f"Couldn't reach GitHub: {exc}") from exc

        if response.is_success:
            return response.json()
        _raise_for_status(response)


def _raise_for_status(response: httpx.Response) -> None:
    status = response.status_code
    try:
        message = response.json().get("message", response.text)
    except ValueError:
        message = response.text

    if status in (403, 429) and response.headers.get("x-ratelimit-remaining") == "0":
        reset = response.headers.get("x-ratelimit-reset")
        reset_at = datetime.fromtimestamp(int(reset), tz=UTC) if reset else None
        raise RateLimitError(
            "GitHub rate limit reached. Set GITHUB_TOKEN to raise it.", reset_at=reset_at
        )
    if status == 404:
        raise NotFoundError(
            "Pull request not found. If the repo is private, set GITHUB_TOKEN with access to it."
        )
    if status in (401, 403):
        raise AuthError(f"GitHub refused the request: {message}")
    raise GitHubError(f"GitHub returned {status}: {message}")


def _to_pull_request(owner: str, repo: str, data: dict[str, Any]) -> PullRequest:
    user = data.get("user")
    return PullRequest(
        owner=owner,
        repo=repo,
        number=data["number"],
        title=data["title"],
        body=data.get("body"),
        state=data["state"],
        draft=data.get("draft", False),
        merged=data.get("merged", False),
        author=GitHubUser(login=user["login"], avatar_url=user.get("avatar_url")) if user else None,
        base_ref=data["base"]["ref"],
        head_ref=data["head"]["ref"],
        base_sha=data["base"]["sha"],
        head_sha=data["head"]["sha"],
        html_url=data["html_url"],
        additions=data.get("additions", 0),
        deletions=data.get("deletions", 0),
        changed_files=data.get("changed_files", 0),
        commits=data.get("commits", 0),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )

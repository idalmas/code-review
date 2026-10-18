import asyncio
import hashlib
import tarfile
import tempfile
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

import httpx

from .types import (
    AuthError,
    ChangedFile,
    GitHubError,
    GitHubUser,
    NotFoundError,
    OAuthExchangeError,
    OAuthTokens,
    PullRequest,
    RateLimitError,
    ReviewComment,
    ValidationFailedError,
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
        api_url: str,
        web_url: str,
        cache_ttl_seconds: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "orbiter",
            },
            timeout=30.0,
            transport=transport,
        )
        self._web_url = web_url.rstrip("/")
        self._cache = _TTLCache(cache_ttl_seconds)

    async def get_pull_request(
        self, owner: str, repo: str, number: int, *, token: str | None
    ) -> PullRequest:
        async def fetch() -> PullRequest:
            data = await self._get_json(f"/repos/{owner}/{repo}/pulls/{number}", token=token)
            return _to_pull_request(owner, repo, data)

        key = ("pr", _token_key(token), owner, repo, number)
        return await self._cache.get_or_fetch(key, fetch)

    async def list_files(
        self, owner: str, repo: str, number: int, *, token: str | None
    ) -> list[ChangedFile]:
        async def fetch() -> list[ChangedFile]:
            files: list[ChangedFile] = []
            for page in range(1, _MAX_PAGES + 1):
                batch = await self._get_json(
                    f"/repos/{owner}/{repo}/pulls/{number}/files",
                    token=token,
                    params={"per_page": _PER_PAGE, "page": page},
                )
                files.extend(ChangedFile.model_validate(item) for item in batch)
                if len(batch) < _PER_PAGE:
                    break
            return files

        key = ("files", _token_key(token), owner, repo, number)
        return await self._cache.get_or_fetch(key, fetch)

    async def list_review_comments(
        self, owner: str, repo: str, number: int, *, token: str | None
    ) -> list[ReviewComment]:
        comments: list[ReviewComment] = []
        for page in range(1, _MAX_PAGES + 1):
            batch = await self._get_json(
                f"/repos/{owner}/{repo}/pulls/{number}/comments",
                token=token,
                params={"per_page": _PER_PAGE, "page": page, "sort": "created", "direction": "asc"},
            )
            comments.extend(_to_review_comment(c) for c in batch)
            if len(batch) < _PER_PAGE:
                break
        return comments

    async def create_review_comment(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        token: str,
        commit_id: str,
        path: str,
        line: int,
        side: str,
        body: str,
        start_line: int | None = None,
    ) -> ReviewComment:
        payload: dict[str, Any] = {
            "body": body, "commit_id": commit_id, "path": path, "line": line, "side": side,
        }  # fmt: skip
        if start_line is not None and start_line < line:
            payload |= {"start_line": start_line, "start_side": side}
        data = await self._post_json(
            f"/repos/{owner}/{repo}/pulls/{number}/comments", token=token, payload=payload
        )
        return _to_review_comment(data)

    async def reply_to_review_comment(
        self, owner: str, repo: str, number: int, comment_id: int, *, token: str, body: str
    ) -> ReviewComment:
        data = await self._post_json(
            f"/repos/{owner}/{repo}/pulls/{number}/comments/{comment_id}/replies",
            token=token,
            payload={"body": body},
        )
        return _to_review_comment(data)

    async def download_tree(
        self, owner: str, repo: str, ref: str, *, token: str | None, dest: Path, max_bytes: int
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "repo.tar.gz"
            await self._download_tarball(
                owner, repo, ref, token=token, dest=archive, max_bytes=max_bytes
            )
            await asyncio.to_thread(_extract, archive, dest, max_bytes * 4)

    async def _download_tarball(
        self, owner: str, repo: str, ref: str, *, token: str | None, dest: Path, max_bytes: int
    ) -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else None
        url = f"/repos/{owner}/{repo}/tarball/{ref}"
        try:
            # GitHub redirects to a signed codeload URL; httpx drops our token on that hop.
            async with self._client.stream(
                "GET", url, headers=headers, follow_redirects=True, timeout=120.0
            ) as response:
                if not response.is_success:
                    await response.aread()
                    _raise_for_status(response)
                written = 0
                with dest.open("wb") as f:
                    async for chunk in response.aiter_bytes():
                        written += len(chunk)
                        if written > max_bytes:
                            raise GitHubError(f"Repository is larger than {max_bytes:,} bytes.")
                        f.write(chunk)
        except httpx.HTTPError as exc:
            raise GitHubError(f"Couldn't download the repository: {exc}") from exc

    async def get_viewer(self, *, token: str) -> GitHubUser:
        data = await self._get_json("/user", token=token)
        return GitHubUser(
            login=data["login"], avatar_url=data.get("avatar_url"), name=data.get("name")
        )

    async def exchange_oauth_code(
        self, *, client_id: str, client_secret: str, code: str, redirect_uri: str
    ) -> OAuthTokens:
        return await self._token_request(
            client_id=client_id, client_secret=client_secret, code=code, redirect_uri=redirect_uri
        )

    async def refresh_oauth_token(
        self, *, client_id: str, client_secret: str, refresh_token: str
    ) -> OAuthTokens:
        return await self._token_request(
            client_id=client_id,
            client_secret=client_secret,
            grant_type="refresh_token",
            refresh_token=refresh_token,
        )

    async def _token_request(self, **form: str) -> OAuthTokens:
        try:
            response = await self._client.post(
                f"{self._web_url}/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data=form,
            )
        except httpx.HTTPError as exc:
            raise GitHubError(f"Couldn't reach GitHub: {exc}") from exc
        # GitHub answers 200 even for bad codes, with an `error` field instead of a token.
        body = response.json() if response.is_success else {}
        if not body.get("access_token"):
            reason = body.get("error_description") or body.get("error") or response.status_code
            raise OAuthExchangeError(f"GitHub sign-in failed: {reason}")
        expires_in = body.get("expires_in")
        return OAuthTokens(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=datetime.now(UTC) + timedelta(seconds=int(expires_in))
            if expires_in
            else None,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _post_json(self, path: str, *, token: str, payload: dict) -> Any:
        try:
            response = await self._client.post(
                path, json=payload, headers={"Authorization": f"Bearer {token}"}
            )
        except httpx.HTTPError as exc:
            raise GitHubError(f"Couldn't reach GitHub: {exc}") from exc
        if response.is_success:
            return response.json()
        _raise_for_status(response)

    async def _get_json(self, path: str, *, token: str | None, params: dict | None = None) -> Any:
        headers = {"Authorization": f"Bearer {token}"} if token else None
        try:
            response = await self._client.get(path, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise GitHubError(f"Couldn't reach GitHub: {exc}") from exc

        if response.is_success:
            return response.json()
        _raise_for_status(response)


def _extract(archive: Path, dest: Path, max_bytes: int) -> None:
    """Unpack GitHub's tarball (one top-level folder) with tarfile's `data` filter, which
    rejects absolute paths, `..`, device files and links that point outside `dest`."""
    total = 0

    def strip_top(member: tarfile.TarInfo, path: str) -> tarfile.TarInfo | None:
        nonlocal total
        _, _, rest = member.name.partition("/")
        if not rest:
            return None
        total += member.size
        if total > max_bytes:
            raise GitHubError("Repository is too large to unpack.")
        changes = {"name": rest}
        if member.islnk():
            changes["linkname"] = member.linkname.partition("/")[2]
        return tarfile.data_filter(member.replace(**changes, deep=False), path)

    dest.mkdir(parents=True)
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(dest, filter=strip_top)


def _token_key(token: str | None) -> str:
    # Never keep raw tokens in cache keys; a hash still separates users.
    return hashlib.sha256(token.encode()).hexdigest() if token else "anonymous"


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
            "GitHub rate limit reached. Sign in with GitHub to raise it.", reset_at=reset_at
        )
    if status == 404:
        raise NotFoundError(
            "Pull request not found. If the repo is private, sign in with a GitHub account "
            "that can see it."
        )
    if status in (401, 403):
        raise AuthError(f"GitHub refused the request: {message}")
    if status == 422:
        errors = (
            response.json().get("errors")
            if "json" in response.headers.get("content-type", "")
            else None
        )
        detail = "; ".join(
            str(e.get("message", e)) if isinstance(e, dict) else str(e) for e in errors or []
        )
        raise ValidationFailedError(f"GitHub rejected it: {detail or message}")
    raise GitHubError(f"GitHub returned {status}: {message}")


def _to_user(data: dict[str, Any] | None) -> GitHubUser | None:
    if not data:
        return None
    return GitHubUser(
        login=data["login"], avatar_url=data.get("avatar_url"), is_bot=data.get("type") == "Bot"
    )


def _to_review_comment(data: dict[str, Any]) -> ReviewComment:
    return ReviewComment(
        id=data["id"],
        path=data["path"],
        line=data.get("line"),
        start_line=data.get("start_line"),
        side=data.get("side"),
        original_line=data.get("original_line"),
        in_reply_to_id=data.get("in_reply_to_id"),
        author=_to_user(data.get("user")),
        body=data.get("body") or "",
        created_at=data["created_at"],
        html_url=data["html_url"],
    )


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
        author=_to_user(user),
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

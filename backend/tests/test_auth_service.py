import asyncio
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from app.services.auth import LoginError, LoginNotConfiguredError, create_auth_service

from .fakes import SAMPLE_FILES, FakeGitHubService, make_pull


def make_auth(**overrides):
    args = dict(
        github=FakeGitHubService(make_pull(), SAMPLE_FILES),
        client_id="cid",
        client_secret="csecret",
        session_secret="s3cret",
        app_url="https://review.example.com",
    )
    args.update(overrides)
    return create_auth_service(**args)


def state_of(authorize_url: str) -> str:
    return parse_qs(urlsplit(authorize_url).query)["state"][0]


async def test_full_login_round_trip() -> None:
    auth = make_auth()
    start = auth.start_login("/acme/api/pull/7")

    query = parse_qs(urlsplit(start.authorize_url).query)
    assert start.authorize_url.startswith("https://github.com/login/oauth/authorize?")
    assert query["redirect_uri"] == ["https://review.example.com/api/auth/callback"]
    assert query["client_id"] == ["cid"]

    result = await auth.complete_login(
        code=FakeGitHubService.VALID_CODE,
        state=state_of(start.authorize_url),
        state_cookie=start.state_cookie,
    )
    assert result.return_to == "/acme/api/pull/7"
    assert FakeGitHubService.TOKEN not in result.session_cookie  # encrypted, not just encoded

    session = (await auth.load_session(result.session_cookie)).session
    assert session.user.login == "octocat"
    assert session.token == FakeGitHubService.TOKEN


async def test_rejects_forged_or_missing_state() -> None:
    auth = make_auth()
    start = auth.start_login("/")
    with pytest.raises(LoginError):
        await auth.complete_login(
            code="good-code", state="attacker", state_cookie=start.state_cookie
        )
    with pytest.raises(LoginError):
        await auth.complete_login(
            code="good-code", state=state_of(start.authorize_url), state_cookie=None
        )


async def test_rejected_code_is_a_login_error() -> None:
    auth = make_auth()
    start = auth.start_login("/")
    with pytest.raises(LoginError):
        await auth.complete_login(
            code="bad", state=state_of(start.authorize_url), state_cookie=start.state_cookie
        )


@pytest.mark.parametrize(
    "return_to",
    [None, "", "https://evil.example", "//evil.example", "/\\evil.example", "/a\r\nX: y"],
)
async def test_return_to_cannot_leave_the_site(return_to) -> None:
    auth = make_auth()
    start = auth.start_login(return_to)
    result = await auth.complete_login(
        code="good-code", state=state_of(start.authorize_url), state_cookie=start.state_cookie
    )
    assert result.return_to == "/"


async def test_sessions_resist_tampering_and_other_keys() -> None:
    auth = make_auth()
    start = auth.start_login("/")
    result = await auth.complete_login(
        code="good-code", state=state_of(start.authorize_url), state_cookie=start.state_cookie
    )

    async def session_of(auth, cookie):
        return (await auth.load_session(cookie)).session

    assert await session_of(auth, None) is None
    assert await session_of(auth, "garbage") is None
    assert await session_of(auth, result.session_cookie[:-4] + "AAAA") is None
    # A state cookie must not be accepted as a session.
    assert await session_of(auth, start.state_cookie) is None
    # Another deployment's secret can't read this deployment's cookies.
    assert await session_of(make_auth(session_secret="other"), result.session_cookie) is None


def test_disabled_without_credentials() -> None:
    auth = make_auth(client_id=None, client_secret=None)
    assert not auth.is_enabled()
    with pytest.raises(LoginNotConfiguredError):
        auth.start_login("/")


async def _github_app_login(lifetime: timedelta):
    github = FakeGitHubService(make_pull(), SAMPLE_FILES)
    github.token_lifetime = lifetime
    auth = make_auth(github=github)
    start = auth.start_login("/")
    result = await auth.complete_login(
        code="good-code", state=state_of(start.authorize_url), state_cookie=start.state_cookie
    )
    return auth, github, result.session_cookie


async def test_github_app_tokens_refresh_once_even_under_concurrency() -> None:
    auth, github, cookie = await _github_app_login(timedelta(minutes=5))  # inside the margin

    loads = await asyncio.gather(*(auth.load_session(cookie) for _ in range(5)))

    assert github.refreshes == ["refresh-1"]  # the single-use token is spent exactly once
    assert {load.session.token for load in loads} == {f"{FakeGitHubService.TOKEN}-1"}
    assert all(load.new_cookie for load in loads)
    # A request still carrying the old cookie (e.g. an image response that couldn't update
    # it) gets the same refreshed session instead of being signed out.
    again = await auth.load_session(cookie)
    assert again.session.token == f"{FakeGitHubService.TOKEN}-1" and github.refreshes == [
        "refresh-1"
    ]


async def test_fresh_github_app_tokens_are_used_as_is() -> None:
    auth, github, cookie = await _github_app_login(timedelta(hours=8))
    load = await auth.load_session(cookie)
    assert load.session.token == FakeGitHubService.TOKEN and load.new_cookie is None
    assert github.refreshes == []


async def test_revoked_refresh_token_signs_out() -> None:
    auth, github, cookie = await _github_app_login(timedelta(minutes=5))
    github.refreshes.append("someone else used it")  # next expected token no longer matches
    load = await auth.load_session(cookie)
    assert load.session is None and load.clear_cookie

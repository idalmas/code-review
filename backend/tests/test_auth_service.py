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

    session = auth.read_session(result.session_cookie)
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
    assert auth.read_session(None) is None
    assert auth.read_session("garbage") is None
    assert auth.read_session(result.session_cookie[:-4] + "AAAA") is None
    # A state cookie must not be accepted as a session.
    assert auth.read_session(start.state_cookie) is None
    # Another deployment's secret can't read this deployment's cookies.
    assert make_auth(session_secret="other").read_session(result.session_cookie) is None


def test_disabled_without_credentials() -> None:
    auth = make_auth(client_id=None, client_secret=None)
    assert not auth.is_enabled()
    with pytest.raises(LoginNotConfiguredError):
        auth.start_login("/")

from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app.api.deps import SESSION_COOKIE, get_auth_service, get_review_service
from app.main import app
from app.services.auth import create_auth_service
from app.services.diff import create_diff_service
from app.services.review import create_review_service

from .fakes import SAMPLE_FILES, FakeGitHubService, make_pull


@pytest.fixture
def github():
    return FakeGitHubService(make_pull(changed_files=4), SAMPLE_FILES)


@pytest.fixture
def client(github):
    review = create_review_service(github=github, diff=create_diff_service())
    auth = create_auth_service(
        github=github,
        client_id="cid",
        client_secret="csecret",
        session_secret="s3cret",
        app_url="http://testserver",
    )
    app.dependency_overrides[get_review_service] = lambda: review
    app.dependency_overrides[get_auth_service] = lambda: auth
    yield TestClient(app, follow_redirects=False)
    app.dependency_overrides.clear()


def sign_in(client: TestClient, return_to: str = "/acme/api/pull/7"):
    res = client.get("/api/auth/login", params={"return_to": return_to})
    assert res.status_code == 302
    state = parse_qs(urlsplit(res.headers["location"]).query)["state"][0]
    return client.get("/api/auth/callback", params={"code": "good-code", "state": state})


def test_health(client) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_resolve_link(client) -> None:
    res = client.post("/api/links/resolve", json={"url": "github.com/acme/api/pull/7/files"})
    assert res.status_code == 200
    assert res.json()["app_path"] == "/acme/api/pull/7"


def test_resolve_link_invalid(client) -> None:
    res = client.post("/api/links/resolve", json={"url": "https://gitlab.com/x/y/pull/1"})
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_link"


def test_review_and_file_diff(client) -> None:
    summary = client.get("/api/repos/acme/api/pulls/7/review").json()
    assert summary["stats"]["files"] == 4

    diff = client.get("/api/repos/acme/api/pulls/7/files/src/A.py").json()
    assert diff["file"]["path"] == "src/A.py"
    assert len(diff["hunks"]) == 1


def test_not_found_errors(client) -> None:
    assert client.get("/api/repos/acme/api/pulls/8/review").json()["code"] == "not_found"
    res = client.get("/api/repos/acme/api/pulls/7/files/missing.py")
    assert res.status_code == 404
    assert res.json()["code"] == "file_not_in_pull_request"


def test_signed_out_me(client) -> None:
    assert client.get("/api/auth/me").json() == {"login_enabled": True, "user": None}


def test_sign_in_then_private_repo_uses_viewer_token(client, github) -> None:
    github.private_to = FakeGitHubService.TOKEN
    assert client.get("/api/repos/acme/api/pulls/7/review").status_code == 404

    res = sign_in(client)
    assert res.status_code == 302
    assert res.headers["location"] == "/acme/api/pull/7"
    cookie = res.headers["set-cookie"]
    assert SESSION_COOKIE in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie

    me = client.get("/api/auth/me").json()
    assert me["user"]["login"] == "octocat"
    assert "token" not in str(me)

    assert client.get("/api/repos/acme/api/pulls/7/review").status_code == 200
    assert github.tokens_seen[-1] == FakeGitHubService.TOKEN

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").json()["user"] is None


def test_callback_errors_redirect_home_with_message(client) -> None:
    res = client.get("/api/auth/callback", params={"code": "good-code", "state": "forged"})
    assert res.status_code == 302
    assert res.headers["location"].startswith("/?login_error=")
    assert SESSION_COOKIE not in res.headers.get("set-cookie", "")

    res = client.get("/api/auth/callback", params={"error": "access_denied"})
    assert res.headers["location"].startswith("/?login_error=")


def test_login_not_configured(client, github) -> None:
    off = create_auth_service(
        github=github, client_id=None, client_secret=None, session_secret="x", app_url="http://t"
    )
    app.dependency_overrides[get_auth_service] = lambda: off
    assert client.get("/api/auth/me").json()["login_enabled"] is False
    res = client.get("/api/auth/login")
    assert res.status_code == 503
    assert res.json()["code"] == "login_not_configured"

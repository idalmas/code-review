from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app.api.deps import SESSION_COOKIE, get_auth_service, get_llm_service, get_review_service
from app.main import app
from app.services.auth import create_auth_service
from app.services.diff import create_diff_service
from app.services.review import create_review_service

from .fakes import SAMPLE_FILES, FakeGitHubService, FakeLLMService, make_pull


@pytest.fixture
def github():
    return FakeGitHubService(make_pull(changed_files=4), SAMPLE_FILES)


@pytest.fixture
def llm():
    return FakeLLMService()


@pytest.fixture
def client(github, llm):
    review = create_review_service(github=github, diff=create_diff_service(), llm=llm)
    auth = create_auth_service(
        github=github,
        client_id="cid",
        client_secret="csecret",
        session_secret="s3cret",
        app_url="http://testserver",
    )
    app.dependency_overrides[get_review_service] = lambda: review
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_llm_service] = lambda: llm
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
    assert client.get("/api/auth/me").json() == {
        "login_enabled": True,
        "user": None,
        "install_url": None,
    }


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


def test_llm_status(client) -> None:
    assert client.get("/api/llm").json()["enabled"] is True


def test_summaries_require_sign_in_then_work(client, llm) -> None:
    body = {"path": "src/A.py", "tier": "balanced"}
    res = client.post("/api/repos/acme/api/pulls/7/summaries", json=body)
    assert res.status_code == 401
    assert res.json()["code"] == "sign_in_required"
    assert llm.requests == []  # no money spent

    sign_in(client)
    res = client.post("/api/repos/acme/api/pulls/7/summaries", json=body)
    assert res.status_code == 200
    assert res.json()["text"] == "Adds two names."
    assert llm.requests[0].tier == "balanced"

    res = client.post("/api/repos/acme/api/pulls/7/summaries", json={"path": "x", "tier": "huge"})
    assert res.status_code == 422


def test_summaries_when_ai_is_off(client, llm) -> None:
    llm.enabled = False
    sign_in(client)
    res = client.post("/api/repos/acme/api/pulls/7/summaries", json={"path": "src/A.py"})
    assert res.status_code == 503
    assert res.json()["code"] == "llm_not_configured"


def test_commenting_requires_sign_in(client, github) -> None:
    body = {"path": "src/A.py", "line": 2, "body": "hi"}
    res = client.post("/api/repos/acme/api/pulls/7/comments", json=body)
    assert (res.status_code, res.json()["code"]) == (401, "sign_in_required")

    sign_in(client)
    res = client.post("/api/repos/acme/api/pulls/7/comments", json=body)
    assert res.status_code == 201
    thread = res.json()
    assert github.posted[0]["token"] == FakeGitHubService.TOKEN

    res = client.post(f"/api/repos/acme/api/pulls/7/comments/{thread['id']}/replies",
                      json={"body": "more"})  # fmt: skip
    assert res.status_code == 201
    threads = client.get("/api/repos/acme/api/pulls/7/comments").json()
    assert [c["body"] for c in threads[0]["comments"]] == ["hi", "more"]

    res = client.post("/api/repos/acme/api/pulls/7/comments", json={**body, "line": 99})
    assert (res.status_code, res.json()["code"]) == (422, "invalid_comment")


def test_expiring_github_app_session_is_refreshed_on_the_response(client, github) -> None:
    github.token_lifetime = timedelta(minutes=5)  # GitHub App token, about to expire
    sign_in(client)
    res = client.get("/api/auth/me")
    assert res.json()["user"]["login"] == "octocat"
    assert SESSION_COOKIE in res.headers["set-cookie"]  # rotated session cookie
    assert github.refreshes == ["refresh-1"]

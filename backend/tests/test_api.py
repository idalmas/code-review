import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_review_service
from app.main import app
from app.services.diff import create_diff_service
from app.services.review import create_review_service

from .fakes import SAMPLE_FILES, FakeGitHubService, make_pull


@pytest.fixture
def client():
    github = FakeGitHubService(make_pull(changed_files=4), SAMPLE_FILES)
    review = create_review_service(github=github, diff=create_diff_service())
    app.dependency_overrides[get_review_service] = lambda: review
    yield TestClient(app)
    app.dependency_overrides.clear()


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

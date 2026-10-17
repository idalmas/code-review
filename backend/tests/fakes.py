from datetime import UTC, datetime

from app.services.github import (
    ChangedFile,
    GitHubUser,
    NotFoundError,
    OAuthExchangeError,
    PullRequest,
)
from app.services.llm import Completion, CompletionRequest, LLMNotConfiguredError, LLMStatus


def make_pull(**overrides) -> PullRequest:
    data = dict(
        owner="acme",
        repo="api",
        number=7,
        title="Add things",
        body=None,
        state="open",
        draft=False,
        merged=False,
        author=None,
        base_ref="main",
        head_ref="feature",
        base_sha="a" * 40,
        head_sha="b" * 40,
        html_url="https://github.com/acme/api/pull/7",
        additions=0,
        deletions=0,
        changed_files=0,
        commits=1,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    data.update(overrides)
    return PullRequest(**data)


class FakeGitHubService:
    VALID_CODE = "good-code"
    TOKEN = "gho_user_token"

    def __init__(self, pull: PullRequest, files: list[ChangedFile]) -> None:
        self.pull = pull
        self.files = files
        self.tokens_seen: list[str | None] = []
        # When set, only this token may read the PR (simulates a private repo).
        self.private_to: str | None = None

    async def get_pull_request(
        self, owner: str, repo: str, number: int, *, token: str | None
    ) -> PullRequest:
        self.tokens_seen.append(token)
        if number != self.pull.number or (self.private_to and token != self.private_to):
            raise NotFoundError("Pull request not found.")
        return self.pull

    async def list_files(
        self, owner: str, repo: str, number: int, *, token: str | None
    ) -> list[ChangedFile]:
        await self.get_pull_request(owner, repo, number, token=token)
        return self.files

    # path -> file contents, per commit sha; served as GitHub-style tarballs.
    trees: dict[str, dict[str, str]] = {}

    async def download_tarball(self, owner, repo, ref, *, token, dest, max_bytes) -> None:
        import io
        import tarfile

        with tarfile.open(dest, "w:gz") as tar:
            for path, text in self.trees[ref].items():
                data = text.encode()
                info = tarfile.TarInfo(f"{owner}-{repo}-{ref[:7]}/{path}")
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))

    async def get_viewer(self, *, token: str) -> GitHubUser:
        return GitHubUser(login="octocat", avatar_url="https://x/a.png", name="Octo Cat")

    async def exchange_oauth_code(
        self, *, client_id: str, client_secret: str, code: str, redirect_uri: str
    ) -> str:
        if code != self.VALID_CODE:
            raise OAuthExchangeError("bad_verification_code")
        return self.TOKEN

    async def aclose(self) -> None:
        pass


SAMPLE_FILES = [
    ChangedFile(
        filename="src/b.py", status="modified", additions=1, deletions=1, changes=2,
        patch="@@ -1 +1 @@\n-a\n+b",
    ),
    ChangedFile(
        filename="package-lock.json", status="modified", additions=500, deletions=400,
        changes=900, patch=None,
    ),
    ChangedFile(
        filename="src/A.py", status="added", additions=2, deletions=0, changes=2,
        patch="@@ -0,0 +1,2 @@\n+x\n+y",
    ),
    ChangedFile(
        filename="logo.png", status="added", additions=0, deletions=0, changes=0, patch=None
    ),
]  # fmt: skip


class FakeLLMService:
    def __init__(self, enabled: bool = True, replies: list[str] | None = None) -> None:
        self.enabled = enabled
        self.requests: list[CompletionRequest] = []
        self.replies = replies or []

    def status(self) -> LLMStatus:
        return LLMStatus(enabled=self.enabled, provider="anthropic" if self.enabled else None,
                         default_tier="cheap", tiers=[])  # fmt: skip

    async def complete(self, request: CompletionRequest) -> Completion:
        if not self.enabled:
            raise LLMNotConfiguredError("AI features are off.")
        self.requests.append(request)
        text = self.replies.pop(0) if self.replies else " Adds two names. \n"
        return Completion(text=text, tier=request.tier, provider="anthropic",
                          model="claude-haiku-5-5", input_tokens=120, output_tokens=12)  # fmt: skip

    async def aclose(self) -> None:
        pass

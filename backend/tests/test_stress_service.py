import asyncio

import pytest

from app.services.github import ChangedFile
from app.services.sandbox import SandboxResult
from app.services.stress import NotStressableError, StressJobNotFoundError, create_stress_service

from .fakes import FakeGitHubService, FakeLLMService, make_pull

TESTS = "```python\nfrom hypothesis import given\n\ndef test_x():\n    assert True\n```"
TREE = {
    "api/pyproject.toml": "[project]\nname='api'\n",
    "api/src/shop/slug.py": "def slugify(s):\n    return s.lower()\n",
}


class FakeSandbox:
    """Install always succeeds; test runs answer from `outcomes[version]` in order."""

    def __init__(self, outcomes: dict[str, list[tuple[int, str]]]) -> None:
        self.outcomes = outcomes
        self.runs: list[dict] = []

    def is_available(self) -> bool:
        return True

    async def run(self, *, image, command, workdir, network, timeout_seconds):
        self.runs.append({"command": command, "network": network})
        if command[0] == "/sandbox/install.sh":
            return SandboxResult(exit_code=0, timed_out=False, output="")
        version = "base" if "/work/base/" in command[-1] else "head"
        assert (workdir / version / "api" / "cr_stress_test.py").read_text().startswith("from")
        code, output = self.outcomes[version].pop(0)
        return SandboxResult(exit_code=code, timed_out=False, output=output)


def make(tmp_path, outcomes, replies, status="modified"):
    pull = make_pull()
    github = FakeGitHubService(pull, [
        ChangedFile(filename="api/src/shop/slug.py", status=status, additions=1, deletions=1,
                    changes=2, patch="@@ -1 +1 @@\n-a\n+b"),
        ChangedFile(filename="README.md", status="modified", additions=1, deletions=0,
                    changes=1, patch="@@ -1 +1 @@\n+x"),
    ])  # fmt: skip
    github.trees = {pull.base_sha: TREE, pull.head_sha: TREE}
    sandbox, llm = FakeSandbox(outcomes), FakeLLMService(replies=replies)
    service = create_stress_service(github=github, llm=llm, sandbox=sandbox, work_dir=tmp_path)
    return service, sandbox, llm


async def run(service, path="api/src/shop/slug.py", viewer="github:octo"):
    job = await service.start("acme", "api", 7, path, tier="balanced", token="t", viewer=viewer)
    for _ in range(200):
        job = service.get(job.id, viewer=viewer)
        if job.status in ("done", "failed", "skipped"):
            return job
        await asyncio.sleep(0.01)
    raise AssertionError("never finished")


async def test_new_failure_is_attributed_to_the_pr(tmp_path) -> None:
    falsified = (1, "FAILED test_x - IndexError\nFalsifying example: slugify(s='')")
    service, sandbox, llm = make(tmp_path, {"head": [falsified], "base": [(0, "1 passed")]},
                                 [TESTS])  # fmt: skip
    job = await run(service)

    assert (job.status, job.verdict, job.language) == ("done", "new_failure", "python")
    assert "Falsifying example" in job.head.output and job.base.passed
    assert job.test_code.startswith("from hypothesis")
    install, *test_runs = sandbox.runs
    assert install == {"command": ["/sandbox/install.sh", "/work/head/api", "/work/base/api"],
                       "network": True}  # fmt: skip
    assert all(r["network"] is False for r in test_runs)  # PR code runs offline
    prompt = llm.requests[0].prompt
    assert "import shop.slug as target" in prompt  # src/ layout handled
    assert "<diff>" in prompt and "def slugify" in prompt
    assert "untrusted" in llm.requests[0].system
    assert not (tmp_path / job.id).exists()  # sources deleted once done


async def test_real_failures_are_not_retried_away(tmp_path) -> None:
    crash = (1, "FAILED test_x - ZeroDivisionError: division by zero")
    service, sandbox, llm = make(tmp_path, {"head": [crash], "base": [crash]}, [TESTS])
    job = await run(service)
    assert job.verdict == "existing_failure"
    assert len(llm.requests) == 1


async def test_tests_that_cannot_load_get_one_retry(tmp_path) -> None:
    broken = (2, "ERROR collecting cr_stress_test.py\nModuleNotFoundError: No module named 'x'")
    service, sandbox, llm = make(tmp_path, {"head": [broken, (0, "3 passed")], "base": [(0, "")]},
                                 [TESTS, TESTS])  # fmt: skip
    job = await run(service)
    assert job.verdict == "passed" and job.message is None
    assert "ModuleNotFoundError" in llm.requests[1].prompt


async def test_new_files_have_no_before(tmp_path) -> None:
    service, _, _ = make(tmp_path, {"head": [(1, "Falsifying example")]}, [TESTS], status="added")
    job = await run(service)
    assert (job.verdict, job.base) == ("failure", None)


async def test_skip(tmp_path) -> None:
    service, sandbox, _ = make(tmp_path, {}, ["SKIP: only constants"])
    job = await run(service)
    assert (job.status, job.message) == ("skipped", "only constants")


async def test_rejects_non_backend_files(tmp_path) -> None:
    service, _, _ = make(tmp_path, {}, [])
    for path in ("README.md", "api/tests/test_slug.py", "web/src/Card.tsx", "api/src/other.py"):
        with pytest.raises(NotStressableError):
            await service.start("acme", "api", 7, path, tier="cheap", token=None, viewer="v")


async def test_jobs_are_private(tmp_path) -> None:
    service, _, _ = make(tmp_path, {"head": [(0, "")], "base": [(0, "")]}, [TESTS])
    job = await run(service)
    with pytest.raises(StressJobNotFoundError):
        service.get(job.id, viewer="github:mallory")


async def test_typescript_backend_files(tmp_path) -> None:
    pull = make_pull()
    tree = {"server/package.json": "{}", "server/src/price.ts": "export const f = () => 1;"}
    github = FakeGitHubService(pull, [
        ChangedFile(filename="server/src/price.ts", status="added", additions=1, deletions=0,
                    changes=1, patch="@@ -0,0 +1 @@\n+export const f = () => 1;"),
    ])  # fmt: skip
    github.trees = {pull.head_sha: tree}

    class Sandbox(FakeSandbox):
        async def run(self, *, image, command, workdir, network, timeout_seconds):
            self.runs.append({"command": command, "network": network})
            return SandboxResult(exit_code=0, timed_out=False, output="# pass 2")

    sandbox, llm = Sandbox({}), FakeLLMService(replies=["```ts\nimport fc from 'fast-check';\n```"])
    service = create_stress_service(github=github, llm=llm, sandbox=sandbox, work_dir=tmp_path)
    job = await run(service, path="server/src/price.ts")

    assert (job.status, job.language, job.verdict) == ("done", "javascript", "passed")
    assert "import * as target from './src/price.ts';" in llm.requests[0].prompt
    assert "import { test } from 'node:test'" in llm.requests[0].prompt
    test_run = sandbox.runs[-1]["command"]
    assert test_run[0] == "node" and test_run[-1] == "/work/head/server/cr-stress.test.mts"


def test_off_unless_enabled(tmp_path) -> None:
    sandbox, llm = FakeSandbox({}), FakeLLMService()
    off = create_stress_service(github=None, llm=llm, sandbox=sandbox, work_dir=tmp_path,
                                enabled=False)  # fmt: skip
    assert off.is_enabled() is False

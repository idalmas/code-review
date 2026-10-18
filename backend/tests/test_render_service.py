import asyncio
import json
from pathlib import Path

import pytest

from app.services.github import ChangedFile
from app.services.render import (
    NotRenderableError,
    RenderJobNotFoundError,
    RenderUnavailableError,
    create_render_service,
)
from app.services.sandbox import SandboxResult

from .fakes import FakeGitHubService, FakeLLMService, make_pull

HARNESS = '```tsx\nimport { Card } from "@target";\nexport const states = [];\n```'
TREE = {
    "web/package.json": '{"dependencies": {"react": "19"}}',
    "web/package-lock.json": "{}",
    "web/src/index.css": "",
    "web/src/Card.tsx": "export function Card() { return <div/>; }",
}


class FakeSandbox:
    """Pretends to be Docker: records runs and writes the reports the renderer would."""

    def __init__(self, head_reports: list[dict]) -> None:
        self.runs: list[dict] = []
        self.head_reports = head_reports

    def is_available(self) -> bool:
        return True

    async def run(self, *, image, command, workdir: Path, network, timeout_seconds):
        self.runs.append({"command": command, "network": network})
        if command[0] == "node":
            spec = json.loads((workdir / "spec.json").read_text())
            report = self.head_reports.pop(0)
            for version in spec["versions"]:
                out = workdir / "out" / version
                out.mkdir(parents=True, exist_ok=True)
                live = spec.get("live") == version and "states" in report
                (out / "report.json").write_text(json.dumps({**report, "live": live}))
                if live:
                    (workdir / "out" / "live").mkdir(exist_ok=True)
                    (workdir / "out" / "live" / "index.html").write_text("<html>")
                for state in report.get("states", []):
                    (out / state["image"]).write_bytes(version.encode())  # base != head pixels
        return SandboxResult(exit_code=0, timed_out=False, output="")


def state(name: str, errors=(), overflow=0) -> dict:
    return {"name": name, "viewport": {"width": 1024, "height": 768}, "image": f"{name}.png",
            "ms": 5, "timedOut": False, "errors": list(errors), "pageOverflow": False,
            "overflowingElements": overflow}  # fmt: skip


def make(tmp_path, *, reports, replies, files=None):
    pull = make_pull()
    github = FakeGitHubService(pull, files or [
        ChangedFile(filename="web/src/Card.tsx", status="modified", additions=1, deletions=1,
                    changes=2, patch="@@ -1 +1 @@\n-a\n+b"),
        ChangedFile(filename="web/src/util.ts", status="modified", additions=1, deletions=0,
                    changes=1, patch="@@ -1 +1 @@\n+x"),
    ])  # fmt: skip
    github.trees = {pull.base_sha: TREE, pull.head_sha: TREE}
    sandbox = FakeSandbox(reports)
    llm = FakeLLMService(replies=replies)
    service = create_render_service(github=github, llm=llm, sandbox=sandbox, work_dir=tmp_path)
    return service, sandbox, llm


async def finish(service, job_id, viewer="github:octo"):
    for _ in range(200):
        job = service.get(job_id, viewer=viewer)
        if job.status in ("done", "failed", "skipped"):
            return job
        await asyncio.sleep(0.01)
    raise AssertionError("render never finished")


async def test_renders_both_versions_offline_after_networked_install(tmp_path) -> None:
    report = {"states": [state("Default"), state("Long name", overflow=2)]}
    service, sandbox, llm = make(tmp_path, reports=[report], replies=[HARNESS])

    job = await service.start("acme", "api", 7, "web/src/Card.tsx", tier="cheap", token="t",
                              viewer="github:octo")  # fmt: skip
    job = await finish(service, job.id)

    assert job.status == "done", job.message
    assert [s.name for s in job.states] == ["Default", "Long name"]
    assert job.states[0].changed is True
    assert job.states[1].problems == ["Content overflows its box"]
    install, render = sandbox.runs
    assert install == {"command": ["/sandbox/install.sh", "/work/base/web", "/work/head/web"],
                       "network": True}  # fmt: skip
    assert render["network"] is False  # PR code never runs with network access
    assert "untrusted" in llm.requests[0].system
    assert "export function Card" in llm.requests[0].prompt
    # Source trees and node_modules are deleted; only screenshots remain.
    assert sorted(p.name for p in (tmp_path / job.id).iterdir()) == [
        "harness.tsx",
        "out",
        "spec.json",
    ]
    assert service.image_path(job.id, "head", 0, viewer="github:octo").read_bytes() == b"head"


async def test_failed_harness_is_retried_once_with_the_errors(tmp_path) -> None:
    broken = {"states": [state("Default", errors=["TypeError: x is undefined"])]}
    fixed = {"states": [state("Default")]}
    service, sandbox, llm = make(tmp_path, reports=[broken, fixed], replies=[HARNESS, HARNESS])

    job = await service.start("acme", "api", 7, "web/src/Card.tsx", tier="best", token=None,
                              viewer="github:octo")  # fmt: skip
    job = await finish(service, job.id)

    assert job.status == "done" and job.message is None
    assert len(llm.requests) == 2
    assert "TypeError: x is undefined" in llm.requests[1].prompt
    assert [r["command"][0] for r in sandbox.runs] == ["/sandbox/install.sh", "node", "node"]


async def test_llm_can_skip_unrenderable_files(tmp_path) -> None:
    service, sandbox, _ = make(tmp_path, reports=[], replies=["SKIP: async server component"])
    job = await service.start("acme", "api", 7, "web/src/Card.tsx", tier="cheap", token=None,
                              viewer="github:octo")  # fmt: skip
    job = await finish(service, job.id)
    assert (job.status, job.message) == ("skipped", "async server component")
    assert [r["command"][0] for r in sandbox.runs] == ["/sandbox/install.sh"]


async def test_only_changed_component_files(tmp_path) -> None:
    service, *_ = make(tmp_path, reports=[], replies=[])
    for path in ("web/src/util.ts", "web/src/Other.tsx", "web/src/Card.test.tsx"):
        with pytest.raises(NotRenderableError):
            await service.start("acme", "api", 7, path, tier="cheap", token=None, viewer="v")


async def test_jobs_are_private_to_their_viewer(tmp_path) -> None:
    service, *_ = make(tmp_path, reports=[{"states": [state("Default")]}], replies=[HARNESS])
    job = await service.start("acme", "api", 7, "web/src/Card.tsx", tier="cheap", token=None,
                              viewer="github:octo")  # fmt: skip
    await finish(service, job.id)
    with pytest.raises(RenderJobNotFoundError):
        service.get(job.id, viewer="github:mallory")
    with pytest.raises(RenderJobNotFoundError):
        service.image_path(job.id, "head", 0, viewer="github:mallory")
    with pytest.raises(RenderJobNotFoundError):
        service.image_path(job.id, "head", 99, viewer="github:octo")


async def test_unavailable_without_sandbox_or_llm(tmp_path) -> None:
    service, sandbox, llm = make(tmp_path, reports=[], replies=[])
    llm.enabled = False
    assert service.is_enabled() is False
    with pytest.raises(RenderUnavailableError):
        await service.start("acme", "api", 7, "web/src/Card.tsx", tier="cheap", token=None,
                            viewer="v")  # fmt: skip


async def test_live_build_is_served_only_with_its_secret(tmp_path) -> None:
    service, *_ = make(tmp_path, reports=[{"states": [state("Default")]}], replies=[HARNESS])
    job = await service.start("acme", "api", 7, "web/src/Card.tsx", tier="cheap", token=None,
                              viewer="github:octo")  # fmt: skip
    job = await finish(service, job.id)
    job_id, _, secret = job.live_path.split("/")
    assert service.live_file(job_id, secret, "index.html").read_text() == "<html>"
    attempts = [
        ("wrong", "index.html"),
        (secret, "../harness.tsx"),
        (secret, "../../out/head/report.json"),
        (secret, "nope.js"),
    ]
    for bad_secret, path in attempts:
        with pytest.raises(RenderJobNotFoundError):
            service.live_file(job_id, bad_secret, path)

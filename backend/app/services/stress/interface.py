from pathlib import Path
from typing import Protocol

from app.services.github import GitHubService
from app.services.llm import LLMService, Tier
from app.services.sandbox import SandboxService

from .types import (
    Language,
    NotStressableError,
    StressJob,
    StressJobNotFoundError,
    StressStatus,
    StressUnavailableError,
    TestRun,
    Verdict,
)

__all__ = [
    "Language",
    "NotStressableError",
    "StressJob",
    "StressJobNotFoundError",
    "StressService",
    "StressStatus",
    "StressUnavailableError",
    "TestRun",
    "Verdict",
    "create_stress_service",
]


class StressService(Protocol):
    """Stress-tests the functions a PR changed in a Python or Node/Bun backend file. An LLM
    writes property-based tests (Hypothesis / fast-check) with extreme inputs; they run in
    the sandbox, offline, against the code before and after the PR."""

    def is_enabled(self) -> bool: ...

    async def start(
        self,
        owner: str,
        repo: str,
        number: int,
        path: str,
        *,
        tier: Tier,
        token: str | None,
        viewer: str,
    ) -> StressJob:
        """Queue a run and return immediately; poll with `get`. Only `viewer` can see it.
        Raises `StressUnavailableError`, `NotStressableError`, or GitHub errors."""
        ...

    def get(self, job_id: str, *, viewer: str) -> StressJob:
        """Raises `StressJobNotFoundError`."""
        ...


def create_stress_service(
    *,
    github: GitHubService,
    llm: LLMService,
    sandbox: SandboxService,
    work_dir: Path,
    image: str = "code-review-sandbox",
) -> StressService:
    from .impl import StressServiceImpl

    return StressServiceImpl(
        github=github, llm=llm, sandbox=sandbox, work_dir=work_dir, image=image
    )

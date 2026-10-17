from pathlib import Path
from typing import Protocol

from app.services.github import GitHubService
from app.services.llm import LLMService, Tier
from app.services.sandbox import SandboxService

from .types import (
    NotRenderableError,
    RenderJob,
    RenderJobNotFoundError,
    RenderState,
    RenderStatus,
    RenderUnavailableError,
    Version,
    VersionShot,
    Viewport,
)

__all__ = [
    "NotRenderableError",
    "RenderJob",
    "RenderJobNotFoundError",
    "RenderService",
    "RenderState",
    "RenderStatus",
    "RenderUnavailableError",
    "Version",
    "VersionShot",
    "Viewport",
    "create_render_service",
]


class RenderService(Protocol):
    """Renders a changed React component before and after the PR, in several states
    (typical + stress), inside the sandbox. An LLM writes the props; code does the rest."""

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
    ) -> RenderJob:
        """Queue a render and return immediately; poll with `get`. `viewer` owns the job:
        nobody else can see its screenshots. Raises `RenderUnavailableError`,
        `NotRenderableError`, or GitHub errors."""
        ...

    def get(self, job_id: str, *, viewer: str) -> RenderJob:
        """Raises `RenderJobNotFoundError`."""
        ...

    def image_path(self, job_id: str, version: Version, index: int, *, viewer: str) -> Path:
        """Screenshot file for one state. Raises `RenderJobNotFoundError`."""
        ...


def create_render_service(
    *,
    github: GitHubService,
    llm: LLMService,
    sandbox: SandboxService,
    work_dir: Path,
    image: str = "code-review-sandbox",
) -> RenderService:
    from .impl import RenderServiceImpl

    return RenderServiceImpl(
        github=github, llm=llm, sandbox=sandbox, work_dir=work_dir, image=image
    )

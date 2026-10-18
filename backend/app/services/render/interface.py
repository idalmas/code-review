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
    "LIVE_CSP",
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


# Headers for the clickable build: always sandboxed (opaque origin, so no access to Orbiter's
# cookies, storage or API, even if opened directly), no network, embeddable only by Orbiter.
LIVE_CSP = (
    "sandbox allow-scripts; default-src 'none'; script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; "
    "connect-src 'none'; form-action 'none'; base-uri 'none'; frame-ancestors 'self'"
)


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

    def live_file(self, job_id: str, secret: str, path: str) -> Path:
        """A file of the clickable head build. Authorized by the secret in `live_path`
        (the sandboxed iframe that loads it can't send cookies). This is the PR's code:
        serve it only with `LIVE_CSP`. Raises `RenderJobNotFoundError`."""
        ...


def create_render_service(
    *,
    github: GitHubService,
    llm: LLMService,
    sandbox: SandboxService,
    work_dir: Path,
    image: str = "orbiter-sandbox",
) -> RenderService:
    from .impl import RenderServiceImpl

    return RenderServiceImpl(
        github=github, llm=llm, sandbox=sandbox, work_dir=work_dir, image=image
    )

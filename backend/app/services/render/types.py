from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.services.llm import Tier

RenderStatus = Literal["queued", "downloading", "writing_harness", "installing", "rendering",
                       "done", "skipped", "failed"]  # fmt: skip
Version = Literal["base", "head"]


class RenderUnavailableError(Exception):
    """Rendering needs both the sandbox (Docker) and an LLM to be configured."""


class NotRenderableError(ValueError):
    """The file isn't a React component file this PR changed."""


class RenderJobNotFoundError(LookupError):
    """No such job for this viewer (unknown, expired, or someone else's)."""


class Viewport(BaseModel):
    width: int
    height: int


class VersionShot(BaseModel):
    image: str
    errors: list[str]
    page_overflow: bool
    overflowing_elements: int
    timed_out: bool
    ms: int


class RenderState(BaseModel):
    name: str
    viewport: Viewport
    base: VersionShot | None
    head: VersionShot | None
    # Pixels differ between base and head (False if either side is missing).
    changed: bool
    # Plain-language problems found in the head version.
    problems: list[str]


class RenderJob(BaseModel):
    id: str
    path: str
    tier: Tier
    status: RenderStatus
    message: str | None = None
    created_at: datetime
    states: list[RenderState] = []
    # "<job id>/live/<secret>": a clickable build of the head version, for click-to-comment.
    # Only ever returned to the job's owner; anyone holding it can load those files.
    live_path: str | None = None

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import (
    get_render_service,
    get_viewer_id,
    get_viewer_token,
    require_viewer_when_login_enabled,
)
from app.services.llm import Tier
from app.services.render import RenderJob, RenderService

router = APIRouter(tags=["renders"])

Render = Annotated[RenderService, Depends(get_render_service)]
Viewer = Annotated[str, Depends(get_viewer_id)]


class RenderAvailability(BaseModel):
    enabled: bool


class StartRender(BaseModel):
    path: str
    tier: Tier = "cheap"


@router.get("/renders")
def render_availability(render: Render) -> RenderAvailability:
    return RenderAvailability(enabled=render.is_enabled())


@router.post(
    "/repos/{owner}/{repo}/pulls/{number}/renders",
    dependencies=[Depends(require_viewer_when_login_enabled)],
    status_code=202,
)
async def start_render(
    owner: str,
    repo: str,
    number: Annotated[int, Path(gt=0)],
    body: StartRender,
    render: Render,
    viewer: Viewer,
    token: Annotated[str | None, Depends(get_viewer_token)],
) -> RenderJob:
    """Render a changed component before/after the PR. Poll GET /renders/{id}."""
    return await render.start(
        owner, repo, number, body.path, tier=body.tier, token=token, viewer=viewer
    )


@router.get("/renders/{job_id}")
def get_render(job_id: str, render: Render, viewer: Viewer) -> RenderJob:
    return render.get(job_id, viewer=viewer)


@router.get("/renders/{job_id}/{version}/{index}.png")
def get_render_image(
    job_id: str,
    version: Literal["base", "head"],
    index: Annotated[int, Path(ge=0)],
    render: Render,
    viewer: Viewer,
) -> FileResponse:
    return FileResponse(
        render.image_path(job_id, version, index, viewer=viewer),
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600"},
    )

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
from app.services.render import LIVE_CSP, RenderJob, RenderService

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


@router.get("/renders/{job_id}/live/{secret}/{path:path}")
def get_live_file(job_id: str, secret: str, path: str, render: Render) -> FileResponse:
    """The clickable build. No cookie check: the sandboxed iframe can't send cookies, so the
    unguessable secret (only given to the job's owner) authorizes it instead."""
    return FileResponse(
        render.live_file(job_id, secret, path or "index.html"),
        headers={
            "Content-Security-Policy": LIVE_CSP,
            "X-Content-Type-Options": "nosniff",
            # The sandboxed frame has an opaque origin ("null"); its module scripts load in
            # CORS mode, so they need this. The URL itself is the secret.
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "private, max-age=3600",
            "Referrer-Policy": "no-referrer",
        },
    )

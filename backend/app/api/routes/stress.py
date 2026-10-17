from typing import Annotated

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel

from app.api.deps import (
    get_stress_service,
    get_viewer_id,
    get_viewer_token,
    require_viewer_when_login_enabled,
)
from app.services.llm import Tier
from app.services.stress import StressJob, StressService

router = APIRouter(tags=["stress"])

Stress = Annotated[StressService, Depends(get_stress_service)]
Viewer = Annotated[str, Depends(get_viewer_id)]


class StressAvailability(BaseModel):
    enabled: bool


class StartStress(BaseModel):
    path: str
    tier: Tier = "cheap"


@router.get("/stress")
def stress_availability(stress: Stress) -> StressAvailability:
    return StressAvailability(enabled=stress.is_enabled())


@router.post(
    "/repos/{owner}/{repo}/pulls/{number}/stress",
    dependencies=[Depends(require_viewer_when_login_enabled)],
    status_code=202,
)
async def start_stress(
    owner: str,
    repo: str,
    number: Annotated[int, Path(gt=0)],
    body: StartStress,
    stress: Stress,
    viewer: Viewer,
    token: Annotated[str | None, Depends(get_viewer_token)],
) -> StressJob:
    """Stress-test the changed functions in a backend file. Poll GET /stress/{id}."""
    return await stress.start(
        owner, repo, number, body.path, tier=body.tier, token=token, viewer=viewer
    )


@router.get("/stress/{job_id}")
def get_stress(job_id: str, stress: Stress, viewer: Viewer) -> StressJob:
    return stress.get(job_id, viewer=viewer)

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_link_service
from app.services.links import LinkService, ResolvedLink

router = APIRouter(prefix="/links", tags=["links"])


class ResolveLinkRequest(BaseModel):
    url: str


@router.post("/resolve")
def resolve_link(
    body: ResolveLinkRequest,
    links: Annotated[LinkService, Depends(get_link_service)],
) -> ResolvedLink:
    """Turn a pasted GitHub PR link into the matching path in this tool."""
    return links.resolve(body.url)

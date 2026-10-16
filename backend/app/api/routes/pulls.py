from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.api.deps import get_review_service
from app.services.review import FileDiff, ReviewService, ReviewSummary

router = APIRouter(prefix="/repos/{owner}/{repo}/pulls/{number}", tags=["pulls"])

Review = Annotated[ReviewService, Depends(get_review_service)]
Number = Annotated[int, Path(gt=0)]


@router.get("/review")
async def get_review(owner: str, repo: str, number: Number, review: Review) -> ReviewSummary:
    """PR metadata and every changed file (no hunks) for the file tree."""
    return await review.get_summary(owner, repo, number)


@router.get("/files/{path:path}")
async def get_file_diff(
    owner: str, repo: str, number: Number, path: str, review: Review
) -> FileDiff:
    """Parsed hunks for a single file."""
    return await review.get_file_diff(owner, repo, number, path)

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel

from app.api.deps import (
    get_review_service,
    get_viewer_token,
    require_token,
    require_viewer_when_login_enabled,
)
from app.services.github import DiffSide, ReviewComment
from app.services.llm import Tier
from app.services.review import (
    CommentThread,
    FileDiff,
    FileSummary,
    ReviewService,
    ReviewSummary,
)

router = APIRouter(prefix="/repos/{owner}/{repo}/pulls/{number}", tags=["pulls"])

Review = Annotated[ReviewService, Depends(get_review_service)]
Token = Annotated[str | None, Depends(get_viewer_token)]
Number = Annotated[int, Path(gt=0)]
WriteToken = Annotated[str, Depends(require_token)]


@router.get("/review")
async def get_review(
    owner: str, repo: str, number: Number, review: Review, token: Token
) -> ReviewSummary:
    """PR metadata and every changed file (no hunks) for the file tree."""
    return await review.get_summary(owner, repo, number, token=token)


@router.get("/files/{path:path}")
async def get_file_diff(
    owner: str, repo: str, number: Number, path: str, review: Review, token: Token
) -> FileDiff:
    """Parsed hunks for a single file."""
    return await review.get_file_diff(owner, repo, number, path, token=token)


class SummarizeRequest(BaseModel):
    path: str
    tier: Tier = "cheap"


@router.post("/summaries", dependencies=[Depends(require_viewer_when_login_enabled)])
async def summarize_file(
    owner: str, repo: str, number: Number, body: SummarizeRequest, review: Review, token: Token
) -> FileSummary:
    """AI explanation of one file's change. Uses the deployment's LLM key."""
    return await review.summarize_file(owner, repo, number, body.path, tier=body.tier, token=token)


class NewComment(BaseModel):
    path: str
    line: int
    side: DiffSide = "RIGHT"
    start_line: int | None = None
    body: str


class NewReply(BaseModel):
    body: str


@router.get("/comments")
async def list_comments(
    owner: str, repo: str, number: Number, review: Review, token: Token
) -> list[CommentThread]:
    """Review threads on the diff, including ones from review bots."""
    return await review.list_threads(owner, repo, number, token=token)


@router.post("/comments", status_code=201)
async def add_comment(
    owner: str, repo: str, number: Number, body: NewComment, review: Review, token: WriteToken
) -> CommentThread:
    """Post a review comment on a diff line, as the signed-in user."""
    return await review.add_comment(
        owner,
        repo,
        number,
        path=body.path,
        line=body.line,
        side=body.side,
        start_line=body.start_line,
        body=body.body,
        token=token,
    )


@router.post("/comments/{thread_id}/replies", status_code=201)
async def reply(
    owner: str,
    repo: str,
    number: Number,
    thread_id: Annotated[int, Path(gt=0)],
    body: NewReply,
    review: Review,
    token: WriteToken,
) -> ReviewComment:
    return await review.reply(owner, repo, number, thread_id, body=body.body, token=token)

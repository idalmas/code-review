"""Maps service errors to HTTP responses so routes stay free of try/except."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.deps import SignInRequiredError
from app.services.auth import LoginNotConfiguredError
from app.services.diff import PatchParseError
from app.services.github import GitHubError, RateLimitError
from app.services.links import InvalidLinkError
from app.services.llm import LLMError
from app.services.render import NotRenderableError, RenderJobNotFoundError, RenderUnavailableError
from app.services.review import (
    DiffTooLargeToSummarizeError,
    FileNotInPullRequestError,
    InvalidCommentError,
    NothingToSummarizeError,
)
from app.services.stress import (
    NotStressableError,
    StressJobNotFoundError,
    StressUnavailableError,
)


def _error(status: int, code: str, message: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "detail": message, **extra})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidLinkError)
    async def _invalid_link(_: Request, exc: InvalidLinkError) -> JSONResponse:
        return _error(400, "invalid_link", str(exc))

    @app.exception_handler(SignInRequiredError)
    async def _sign_in(_: Request, exc: SignInRequiredError) -> JSONResponse:
        return _error(401, "sign_in_required", str(exc))

    @app.exception_handler(InvalidCommentError)
    async def _bad_comment(_: Request, exc: InvalidCommentError) -> JSONResponse:
        return _error(422, "invalid_comment", str(exc))

    @app.exception_handler(NothingToSummarizeError)
    async def _nothing(_: Request, exc: NothingToSummarizeError) -> JSONResponse:
        return _error(422, "nothing_to_summarize", str(exc))

    @app.exception_handler(DiffTooLargeToSummarizeError)
    async def _too_large(_: Request, exc: DiffTooLargeToSummarizeError) -> JSONResponse:
        return _error(413, "diff_too_large", str(exc))

    @app.exception_handler(RenderUnavailableError)
    async def _render_off(_: Request, exc: RenderUnavailableError) -> JSONResponse:
        return _error(503, "render_unavailable", str(exc))

    @app.exception_handler(NotRenderableError)
    async def _not_renderable(_: Request, exc: NotRenderableError) -> JSONResponse:
        return _error(422, "not_renderable", str(exc))

    @app.exception_handler(RenderJobNotFoundError)
    async def _render_missing(_: Request, exc: RenderJobNotFoundError) -> JSONResponse:
        return _error(404, "render_not_found", str(exc))

    @app.exception_handler(StressUnavailableError)
    async def _stress_off(_: Request, exc: StressUnavailableError) -> JSONResponse:
        return _error(503, "stress_unavailable", str(exc))

    @app.exception_handler(NotStressableError)
    async def _not_stressable(_: Request, exc: NotStressableError) -> JSONResponse:
        return _error(422, "not_stressable", str(exc))

    @app.exception_handler(StressJobNotFoundError)
    async def _stress_missing(_: Request, exc: StressJobNotFoundError) -> JSONResponse:
        return _error(404, "stress_not_found", str(exc))

    @app.exception_handler(LLMError)
    async def _llm(_: Request, exc: LLMError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message)

    @app.exception_handler(LoginNotConfiguredError)
    async def _login_off(_: Request, exc: LoginNotConfiguredError) -> JSONResponse:
        return _error(503, "login_not_configured", str(exc))

    @app.exception_handler(FileNotInPullRequestError)
    async def _file_missing(_: Request, exc: FileNotInPullRequestError) -> JSONResponse:
        return _error(404, "file_not_in_pull_request", str(exc))

    @app.exception_handler(PatchParseError)
    async def _bad_patch(_: Request, exc: PatchParseError) -> JSONResponse:
        return _error(502, "unparseable_patch", str(exc))

    @app.exception_handler(GitHubError)
    async def _github(_: Request, exc: GitHubError) -> JSONResponse:
        extra = {}
        if isinstance(exc, RateLimitError) and exc.reset_at:
            extra["reset_at"] = exc.reset_at.isoformat()
        return _error(exc.status_code, exc.code, exc.message, **extra)

"""Maps service errors to HTTP responses so routes stay free of try/except."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.services.auth import LoginNotConfiguredError
from app.services.diff import PatchParseError
from app.services.github import GitHubError, RateLimitError
from app.services.links import InvalidLinkError
from app.services.review import FileNotInPullRequestError


def _error(status: int, code: str, message: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "detail": message, **extra})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidLinkError)
    async def _invalid_link(_: Request, exc: InvalidLinkError) -> JSONResponse:
        return _error(400, "invalid_link", str(exc))

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

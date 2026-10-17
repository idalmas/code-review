from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.api.deps import SESSION_COOKIE, STATE_COOKIE, get_auth_service, get_session
from app.config import get_settings
from app.services.auth import STATE_TTL_SECONDS, AuthService, LoginError, Session
from app.services.github import GitHubUser

router = APIRouter(prefix="/auth", tags=["auth"])

Auth = Annotated[AuthService, Depends(get_auth_service)]


class Me(BaseModel):
    login_enabled: bool
    user: GitHubUser | None


@router.get("/me")
def me(auth: Auth, session: Annotated[Session | None, Depends(get_session)]) -> Me:
    """Who's signed in. Never returns the token."""
    return Me(login_enabled=auth.is_enabled(), user=session.user if session else None)


@router.get("/login")
def login(auth: Auth, return_to: str | None = None) -> RedirectResponse:
    """Redirects to GitHub's consent screen."""
    start = auth.start_login(return_to)
    response = RedirectResponse(start.authorize_url, status_code=302)
    _set_cookie(response, STATE_COOKIE, start.state_cookie, STATE_TTL_SECONDS, path="/api/auth")
    return response


@router.get("/callback")
async def callback(
    request: Request,
    auth: Auth,
    code: str | None = None,
    state: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse:
    """GitHub sends the browser here after consent."""
    try:
        if not code or not state:
            raise LoginError(error_description or "GitHub sign-in was cancelled.")
        result = await auth.complete_login(
            code=code, state=state, state_cookie=request.cookies.get(STATE_COOKIE)
        )
    except LoginError as exc:
        response = RedirectResponse(f"/?login_error={quote(str(exc))}", status_code=302)
    else:
        response = RedirectResponse(result.return_to, status_code=302)
        max_age = get_settings().session_max_age_days * 24 * 3600
        _set_cookie(response, SESSION_COOKIE, result.session_cookie, max_age, path="/")
    response.delete_cookie(STATE_COOKIE, path="/api/auth")
    return response


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def _set_cookie(response: Response, name: str, value: str, max_age: int, *, path: str) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path=path,
        httponly=True,
        samesite="lax",
        secure=get_settings().secure_cookies,
    )

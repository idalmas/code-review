from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.api.deps import SESSION_COOKIE, STATE_COOKIE, get_auth_service, get_session, set_cookie
from app.config import get_settings
from app.services.auth import STATE_TTL_SECONDS, AuthService, LoginError, Session
from app.services.github import GitHubUser

router = APIRouter(prefix="/auth", tags=["auth"])

Auth = Annotated[AuthService, Depends(get_auth_service)]


class Me(BaseModel):
    login_enabled: bool
    user: GitHubUser | None
    # Where to install the GitHub App on more repos (when GITHUB_APP_SLUG is set).
    install_url: str | None = None


@router.get("/me")
def me(auth: Auth, session: Annotated[Session | None, Depends(get_session)]) -> Me:
    """Who's signed in. Never returns the token."""
    settings = get_settings()
    slug = settings.github_app_slug
    return Me(
        login_enabled=auth.is_enabled(),
        user=session.user if session else None,
        install_url=f"{settings.github_web_url}/apps/{slug}/installations/new" if slug else None,
    )


@router.get("/login")
def login(auth: Auth, return_to: str | None = None) -> RedirectResponse:
    """Redirects to GitHub's consent screen."""
    start = auth.start_login(return_to)
    response = RedirectResponse(start.authorize_url, status_code=302)
    set_cookie(response, STATE_COOKIE, start.state_cookie, STATE_TTL_SECONDS, path="/api/auth")
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
        set_cookie(response, SESSION_COOKIE, result.session_cookie, max_age, path="/")
    response.delete_cookie(STATE_COOKIE, path="/api/auth")
    return response


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")

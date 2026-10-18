"""Wires services together. Routes get services from here via `Depends`."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request, Response

from app.config import get_settings
from app.services.auth import AuthService, Session, create_auth_service
from app.services.diff import DiffService, create_diff_service
from app.services.github import GitHubService, create_github_service
from app.services.links import LinkService, create_link_service
from app.services.llm import LLMService, create_llm_service
from app.services.render import RenderService, create_render_service
from app.services.review import ReviewService, create_review_service
from app.services.sandbox import SandboxService, create_sandbox_service
from app.services.stress import StressService, create_stress_service

SESSION_COOKIE = "cr_session"
STATE_COOKIE = "cr_oauth_state"


@lru_cache
def get_link_service() -> LinkService:
    return create_link_service()


@lru_cache
def get_diff_service() -> DiffService:
    return create_diff_service()


@lru_cache
def get_github_service() -> GitHubService:
    settings = get_settings()
    return create_github_service(
        api_url=settings.github_api_url,
        web_url=settings.github_web_url,
        cache_ttl_seconds=settings.cache_ttl_seconds,
    )


@lru_cache
def get_llm_service() -> LLMService:
    settings = get_settings()
    overrides = {
        "cheap": settings.llm_model_cheap,
        "balanced": settings.llm_model_balanced,
        "best": settings.llm_model_best,
    }
    return create_llm_service(
        provider=settings.llm_provider,
        anthropic_api_key=settings.anthropic_api_key,
        openai_api_key=settings.openai_api_key,
        model_overrides={tier: model for tier, model in overrides.items() if model},
        anthropic_server_fallbacks=settings.anthropic_server_fallbacks,
    )


@lru_cache
def get_review_service() -> ReviewService:
    return create_review_service(
        github=get_github_service(), diff=get_diff_service(), llm=get_llm_service()
    )


@lru_cache
def get_sandbox_service() -> SandboxService:
    settings = get_settings()
    return create_sandbox_service(
        enabled=settings.sandbox_enabled,
        network_mode=settings.sandbox_install_network,
        proxy=settings.sandbox_install_proxy,
        ca_file=settings.sandbox_install_ca_file,
    )


@lru_cache
def get_render_service() -> RenderService:
    settings = get_settings()
    return create_render_service(
        github=get_github_service(),
        llm=get_llm_service(),
        sandbox=get_sandbox_service(),
        work_dir=Path(settings.sandbox_work_dir) / "renders",
        image=settings.sandbox_image,
    )


@lru_cache
def get_stress_service() -> StressService:
    settings = get_settings()
    return create_stress_service(
        github=get_github_service(),
        llm=get_llm_service(),
        sandbox=get_sandbox_service(),
        work_dir=Path(settings.sandbox_work_dir) / "stress",
        image=settings.sandbox_image,
    )


@lru_cache
def get_auth_service() -> AuthService:
    settings = get_settings()
    return create_auth_service(
        github=get_github_service(),
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        session_secret=settings.session_secret,
        app_url=settings.app_url,
        github_web_url=settings.github_web_url,
        scopes=settings.github_oauth_scopes,
        session_max_age_seconds=settings.session_max_age_days * 24 * 3600,
    )


def set_cookie(response: Response, name: str, value: str, max_age: int, *, path: str) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path=path,
        httponly=True,
        samesite="lax",
        secure=get_settings().secure_cookies,
    )


async def get_session(
    request: Request,
    response: Response,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> Session | None:
    loaded = await auth.load_session(request.cookies.get(SESSION_COOKIE))
    if loaded.new_cookie:  # GitHub App token was refreshed
        max_age = get_settings().session_max_age_days * 24 * 3600
        set_cookie(response, SESSION_COOKIE, loaded.new_cookie, max_age, path="/")
    elif loaded.clear_cookie:
        response.delete_cookie(SESSION_COOKIE, path="/")
    return loaded.session


def get_viewer_token(session: Annotated[Session | None, Depends(get_session)]) -> str | None:
    return session.token if session else None


def get_viewer_id(session: Annotated[Session | None, Depends(get_session)]) -> str:
    """Who owns per-user results such as renders. Everyone shares "anonymous" only when
    sign-in is off (local use); with sign-in on, the endpoints that create them require it."""
    return f"github:{session.user.login}" if session else "anonymous"


class SignInRequiredError(Exception):
    """Raised when an endpoint needs a signed-in user: writes to GitHub, and anything that
    spends the deployment's money (AI)."""


def require_viewer_when_login_enabled(
    auth: Annotated[AuthService, Depends(get_auth_service)],
    session: Annotated[Session | None, Depends(get_session)],
) -> None:
    if auth.is_enabled() and session is None:
        raise SignInRequiredError("Sign in with GitHub to use AI features.")


def require_token(token: Annotated[str | None, Depends(get_viewer_token)]) -> str:
    """For writes to GitHub, which always happen as the signed-in user."""
    if token is None:
        raise SignInRequiredError("Sign in with GitHub to comment.")
    return token

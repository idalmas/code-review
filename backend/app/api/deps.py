"""Wires services together. Routes get services from here via `Depends`."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from app.config import get_settings
from app.services.auth import AuthService, Session, create_auth_service
from app.services.diff import DiffService, create_diff_service
from app.services.github import GitHubService, create_github_service
from app.services.links import LinkService, create_link_service
from app.services.review import ReviewService, create_review_service

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
def get_review_service() -> ReviewService:
    return create_review_service(github=get_github_service(), diff=get_diff_service())


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


def get_session(
    request: Request, auth: Annotated[AuthService, Depends(get_auth_service)]
) -> Session | None:
    return auth.read_session(request.cookies.get(SESSION_COOKIE))


def get_viewer_token(session: Annotated[Session | None, Depends(get_session)]) -> str | None:
    return session.token if session else None

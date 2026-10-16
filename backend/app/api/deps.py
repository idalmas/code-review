"""Wires services together. Routes get services from here via `Depends`."""

from functools import lru_cache

from app.config import get_settings
from app.services.diff import DiffService, create_diff_service
from app.services.github import GitHubService, create_github_service
from app.services.links import LinkService, create_link_service
from app.services.review import ReviewService, create_review_service


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
        token=settings.github_token,
        api_url=settings.github_api_url,
        cache_ttl_seconds=settings.cache_ttl_seconds,
    )


@lru_cache
def get_review_service() -> ReviewService:
    return create_review_service(github=get_github_service(), diff=get_diff_service())

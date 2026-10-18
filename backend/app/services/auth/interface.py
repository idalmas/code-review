from typing import Protocol

from app.services.github import GitHubService

from .types import (
    LoginError,
    LoginNotConfiguredError,
    LoginResult,
    LoginStart,
    Session,
    SessionLoad,
)

__all__ = [
    "AuthService",
    "LoginError",
    "LoginNotConfiguredError",
    "LoginResult",
    "LoginStart",
    "Session",
    "SessionLoad",
    "STATE_TTL_SECONDS",
    "create_auth_service",
]

# How long a user has to finish signing in on GitHub.
STATE_TTL_SECONDS = 600


class AuthService(Protocol):
    """Sign in with GitHub, as a GitHub App (recommended: fine-grained permissions, expiring
    tokens) or an OAuth app. Stateless: sessions live in encrypted cookies, so there is no
    database and nothing to back up or breach server-side."""

    def is_enabled(self) -> bool:
        """False until a GitHub OAuth app's client ID and secret are configured."""
        ...

    def start_login(self, return_to: str | None) -> LoginStart:
        """Begin sign-in. `return_to` is where to land afterwards; anything that isn't a
        same-site path is replaced with `/`. Raises `LoginNotConfiguredError`."""
        ...

    async def complete_login(
        self, *, code: str, state: str, state_cookie: str | None
    ) -> LoginResult:
        """Finish sign-in from GitHub's callback. Raises `LoginError`."""
        ...

    async def load_session(self, session_cookie: str | None) -> SessionLoad:
        """The signed-in session (None if missing, expired or tampered with), refreshing
        GitHub App tokens shortly before they expire. Callers must apply `new_cookie` /
        `clear_cookie` to the response."""
        ...


def create_auth_service(
    *,
    github: GitHubService,
    client_id: str | None,
    client_secret: str | None,
    session_secret: str,
    app_url: str,
    github_web_url: str = "https://github.com",
    scopes: str = "repo read:user",
    session_max_age_seconds: int = 30 * 24 * 3600,
) -> AuthService:
    from .impl import AuthServiceImpl

    return AuthServiceImpl(
        github=github,
        client_id=client_id,
        client_secret=client_secret,
        session_secret=session_secret,
        app_url=app_url,
        github_web_url=github_web_url,
        scopes=scopes,
        session_max_age_seconds=session_max_age_seconds,
    )

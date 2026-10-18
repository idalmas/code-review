from datetime import datetime

from pydantic import BaseModel

from app.services.github import GitHubUser


class LoginNotConfiguredError(Exception):
    """GitHub login needs GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET to be set."""


class LoginError(Exception):
    """The OAuth round trip failed: denied, expired, tampered with, or rejected by GitHub."""


class Session(BaseModel):
    user: GitHubUser
    # The viewer's GitHub token. Only ever stored encrypted, in an httpOnly cookie.
    token: str
    # GitHub App user tokens expire (8h) and come with a single-use refresh token.
    refresh_token: str | None = None
    expires_at: datetime | None = None


class SessionLoad(BaseModel):
    session: Session | None
    # Set when the session was refreshed: store this as the new session cookie.
    new_cookie: str | None = None
    # Set when the session can't be used any more (refresh failed): delete the cookie.
    clear_cookie: bool = False


class LoginStart(BaseModel):
    authorize_url: str
    # Opaque, encrypted value the caller must hand back to `complete_login` (via a cookie).
    state_cookie: str


class LoginResult(BaseModel):
    session: Session
    # Opaque, encrypted value to store in the session cookie.
    session_cookie: str
    # Always a same-site path, safe to redirect to.
    return_to: str

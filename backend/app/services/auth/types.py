from pydantic import BaseModel

from app.services.github import GitHubUser


class LoginNotConfiguredError(Exception):
    """GitHub login needs GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET to be set."""


class LoginError(Exception):
    """The OAuth round trip failed: denied, expired, tampered with, or rejected by GitHub."""


class Session(BaseModel):
    user: GitHubUser
    # The viewer's GitHub OAuth token. Only ever stored encrypted, in an httpOnly cookie.
    token: str


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

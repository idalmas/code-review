import base64
import hashlib
import hmac
import json
import secrets
from urllib.parse import urlencode

from cryptography.fernet import Fernet, InvalidToken

from app.services.github import GitHubError, GitHubService, GitHubUser

from .interface import STATE_TTL_SECONDS
from .types import LoginError, LoginNotConfiguredError, LoginResult, LoginStart, Session


class AuthServiceImpl:
    def __init__(
        self,
        *,
        github: GitHubService,
        client_id: str | None,
        client_secret: str | None,
        session_secret: str,
        app_url: str,
        github_web_url: str,
        scopes: str,
        session_max_age_seconds: int,
    ) -> None:
        self._github = github
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = f"{app_url.rstrip('/')}/api/auth/callback"
        self._authorize_url = f"{github_web_url.rstrip('/')}/login/oauth/authorize"
        self._scopes = scopes
        self._session_max_age = session_max_age_seconds
        key = base64.urlsafe_b64encode(hashlib.sha256(session_secret.encode()).digest())
        self._fernet = Fernet(key)

    def is_enabled(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def start_login(self, return_to: str | None) -> LoginStart:
        if not self.is_enabled():
            raise LoginNotConfiguredError(
                "GitHub sign-in isn't set up. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET."
            )
        state = secrets.token_urlsafe(32)
        query = urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "scope": self._scopes,
                "state": state,
                "allow_signup": "false",
            }
        )
        return LoginStart(
            authorize_url=f"{self._authorize_url}?{query}",
            state_cookie=self._seal(
                {"kind": "state", "state": state, "return_to": _safe_path(return_to)}
            ),
        )

    async def complete_login(
        self, *, code: str, state: str, state_cookie: str | None
    ) -> LoginResult:
        if not self.is_enabled():
            raise LoginNotConfiguredError("GitHub sign-in isn't set up.")
        saved = self._unseal(state_cookie, kind="state", ttl=STATE_TTL_SECONDS)
        # The state ties GitHub's callback to the browser that started the login (CSRF).
        if saved is None or not hmac.compare_digest(saved["state"], state):
            raise LoginError("Sign-in expired or was started in another browser. Try again.")

        try:
            token = await self._github.exchange_oauth_code(
                client_id=self._client_id,
                client_secret=self._client_secret,
                code=code,
                redirect_uri=self._redirect_uri,
            )
            user = await self._github.get_viewer(token=token)
        except GitHubError as exc:
            raise LoginError(exc.message) from exc

        session = Session(user=user, token=token)
        return LoginResult(
            session=session,
            session_cookie=self._seal({"kind": "session", **session.model_dump()}),
            return_to=saved["return_to"],
        )

    def read_session(self, session_cookie: str | None) -> Session | None:
        data = self._unseal(session_cookie, kind="session", ttl=self._session_max_age)
        if data is None:
            return None
        return Session(user=GitHubUser.model_validate(data["user"]), token=data["token"])

    def _seal(self, payload: dict) -> str:
        return self._fernet.encrypt(json.dumps(payload).encode()).decode()

    def _unseal(self, value: str | None, *, kind: str, ttl: int) -> dict | None:
        if not value:
            return None
        try:
            data = json.loads(self._fernet.decrypt(value.encode(), ttl=ttl))
        except (InvalidToken, ValueError):
            return None
        return data if data.get("kind") == kind else None


def _safe_path(return_to: str | None) -> str:
    """Only allow same-site absolute paths, so sign-in can't bounce users to another site."""
    if not return_to or not return_to.startswith("/") or return_to.startswith(("//", "/\\")):
        return "/"
    if any(c in return_to for c in "\r\n"):
        return "/"
    return return_to

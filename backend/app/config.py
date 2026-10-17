import logging
import secrets
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Public URL people open in the browser (the Next.js app). GitHub redirects back here.
    app_url: str = "http://localhost:3000"

    # GitHub OAuth app (Settings → Developer settings → OAuth Apps).
    # Callback URL to register: {app_url}/api/auth/callback
    github_client_id: str | None = None
    github_client_secret: str | None = None
    github_oauth_scopes: str = "repo read:user"

    # Change both for GitHub Enterprise Server, e.g. https://ghe.example.com(/api/v3).
    github_web_url: str = "https://github.com"
    github_api_url: str = "https://api.github.com"

    # Encrypts session cookies. Without it, a random key is used and restarts sign everyone out.
    session_secret: str | None = None
    session_max_age_days: int = 30

    cors_origins: str = "http://localhost:3000"
    cache_ttl_seconds: int = 120

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def secure_cookies(self) -> bool:
        return self.app_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.session_secret:
        log.warning("SESSION_SECRET is not set; using a random one. Restarts will sign users out.")
        settings.session_secret = secrets.token_urlsafe(32)
    return settings

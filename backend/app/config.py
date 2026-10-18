import logging
import secrets
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Public URL people open in the browser (the Next.js app). GitHub redirects back here.
    app_url: str = "http://localhost:3000"

    # GitHub App (recommended) or OAuth app credentials. See docs/self-hosting.md.
    # Callback URL to register: {app_url}/api/auth/callback
    github_client_id: str | None = None
    github_client_secret: str | None = None
    # The App's URL name (github.com/apps/<slug>), for "install on more repos" links.
    github_app_slug: str | None = None
    # Only used by OAuth apps; GitHub Apps get their permissions from the App's settings.
    github_oauth_scopes: str = "repo read:user"

    # Change both for GitHub Enterprise Server, e.g. https://ghe.example.com(/api/v3).
    github_web_url: str = "https://github.com"
    github_api_url: str = "https://api.github.com"

    # Encrypts session cookies. Without it, a random key is used and restarts sign everyone out.
    session_secret: str | None = None
    session_max_age_days: int = 30

    # AI features. Set one key (or both plus LLM_PROVIDER). No key = AI features hidden.
    llm_provider: Literal["anthropic", "openai"] | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    # Override the model behind each user-facing tier.
    llm_model_cheap: str | None = None
    llm_model_balanced: str | None = None
    llm_model_best: str | None = None
    # Re-run Anthropic refusals on a recommended fallback model (Sonnet/Opus only).
    anthropic_server_fallbacks: bool = True

    # Renders and stress tests run PR code in Docker containers (see docs/self-hosting.md).
    sandbox_enabled: bool = False
    sandbox_image: str = "orbiter-sandbox"
    sandbox_work_dir: str = "/tmp/orbiter"
    # Only used while installing dependencies; running PR code never has network access.
    sandbox_install_network: str = "bridge"
    sandbox_install_proxy: str | None = None
    sandbox_install_ca_file: str | None = None

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

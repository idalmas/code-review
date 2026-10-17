from typing import Protocol

from .types import (
    Completion,
    CompletionRequest,
    Effort,
    LLMError,
    LLMNotConfiguredError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMStatus,
    Provider,
    Tier,
    TierConfig,
    TierInfo,
)

__all__ = [
    "DEFAULT_TIERS",
    "Completion",
    "CompletionRequest",
    "Effort",
    "LLMError",
    "LLMNotConfiguredError",
    "LLMRateLimitError",
    "LLMRefusalError",
    "LLMService",
    "LLMStatus",
    "Provider",
    "Tier",
    "TierConfig",
    "TierInfo",
    "create_llm_service",
]

# What each user-facing tier maps to per provider. Every model is overridable via settings.
DEFAULT_TIERS: dict[Provider, dict[Tier, TierConfig]] = {
    "anthropic": {
        "cheap": TierConfig(model="claude-haiku-5-5", effort="low"),
        "balanced": TierConfig(model="claude-sonnet-5-5", effort="medium"),
        "best": TierConfig(model="claude-opus-5-5", effort="high"),
    },
    "openai": {
        "cheap": TierConfig(model="gpt-5-nano", effort="low"),
        "balanced": TierConfig(model="gpt-5-mini", effort="medium"),
        "best": TierConfig(model="gpt-5", effort="high"),
    },
}


class LLMService(Protocol):
    """One place to call a language model. Callers pick a *tier* (cheap / balanced / best),
    never a provider or model: those are deployment config, chosen by whoever self-hosts."""

    def status(self) -> LLMStatus:
        """Whether AI features are on, which provider, and what each tier runs."""
        ...

    async def complete(self, request: CompletionRequest) -> Completion:
        """Single-turn completion. Raises `LLMNotConfiguredError`, `LLMRefusalError`,
        `LLMRateLimitError`, or `LLMError`."""
        ...

    async def aclose(self) -> None:
        """Release network resources. Call on app shutdown."""
        ...


def create_llm_service(
    *,
    provider: Provider | None = None,
    anthropic_api_key: str | None = None,
    openai_api_key: str | None = None,
    model_overrides: dict[Tier, str] | None = None,
    anthropic_server_fallbacks: bool = True,
) -> LLMService:
    """`provider` picks which key to use when both are set; with one key it's inferred.
    With no key, the service reports `enabled=False` and `complete` raises."""
    from .impl import LLMServiceImpl

    return LLMServiceImpl(
        provider=provider,
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
        model_overrides=model_overrides or {},
        anthropic_server_fallbacks=anthropic_server_fallbacks,
    )

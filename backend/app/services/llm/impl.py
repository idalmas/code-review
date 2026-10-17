from typing import Protocol

from .interface import DEFAULT_TIERS
from .types import (
    Completion,
    CompletionRequest,
    LLMNotConfiguredError,
    LLMStatus,
    Provider,
    Tier,
    TierConfig,
    TierInfo,
)

_TIER_COPY: dict[Tier, tuple[str, str]] = {
    "cheap": ("Cheap", "Fast and inexpensive. Good for quick summaries."),
    "balanced": ("Balanced", "Better judgment at moderate cost."),
    "best": ("Best", "Most capable model. Slower and most expensive."),
}


class _Provider(Protocol):
    async def complete(self, config: TierConfig, request: CompletionRequest) -> Completion: ...
    async def aclose(self) -> None: ...


class LLMServiceImpl:
    def __init__(
        self,
        *,
        provider: Provider | None,
        anthropic_api_key: str | None,
        openai_api_key: str | None,
        model_overrides: dict[Tier, str],
        anthropic_server_fallbacks: bool,
        _client: _Provider | None = None,
    ) -> None:
        self._provider_name = _pick_provider(provider, anthropic_api_key, openai_api_key)
        self._tiers: dict[Tier, TierConfig] = {}
        self._client: _Provider | None = _client

        if self._provider_name:
            defaults = DEFAULT_TIERS[self._provider_name]
            self._tiers = {
                tier: cfg.model_copy(update={"model": model_overrides.get(tier) or cfg.model})
                for tier, cfg in defaults.items()
            }
        if self._client is None and self._provider_name == "anthropic":
            from ._anthropic import _AnthropicProvider

            self._client = _AnthropicProvider(
                api_key=anthropic_api_key, server_fallbacks=anthropic_server_fallbacks
            )
        elif self._client is None and self._provider_name == "openai":
            from ._openai import _OpenAIProvider

            self._client = _OpenAIProvider(api_key=openai_api_key)

    def status(self) -> LLMStatus:
        return LLMStatus(
            enabled=self._client is not None,
            provider=self._provider_name,
            default_tier="cheap",
            tiers=[
                TierInfo(tier=tier, label=label, description=desc, model=self._tiers[tier].model)
                for tier, (label, desc) in _TIER_COPY.items()
                if tier in self._tiers
            ],
        )

    async def complete(self, request: CompletionRequest) -> Completion:
        if self._client is None:
            raise LLMNotConfiguredError(
                "AI features are off. Set ANTHROPIC_API_KEY or OPENAI_API_KEY to turn them on."
            )
        return await self._client.complete(self._tiers[request.tier], request)

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()


def _pick_provider(
    requested: Provider | None, anthropic_key: str | None, openai_key: str | None
) -> Provider | None:
    keys: dict[Provider, str | None] = {"anthropic": anthropic_key, "openai": openai_key}
    if requested:
        if not keys[requested]:
            raise LLMNotConfiguredError(f"LLM_PROVIDER={requested} but its API key isn't set.")
        return requested
    if anthropic_key:
        return "anthropic"
    if openai_key:
        return "openai"
    return None

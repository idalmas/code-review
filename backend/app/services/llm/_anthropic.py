"""Anthropic provider. Private to the llm service."""

import anthropic

from .types import (
    Completion,
    CompletionRequest,
    LLMError,
    LLMRateLimitError,
    LLMRefusalError,
    TierConfig,
)

# Server-side refusal fallback: if the model declines, the API re-runs the request on the
# model Anthropic recommends for that refusal category, inside the same call.
# Not offered on Haiku, where a declined request just stays declined.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_FALLBACK_MODEL_PREFIXES = ("claude-opus-", "claude-sonnet-", "claude-fable-")


class _AnthropicProvider:
    def __init__(self, *, api_key: str, server_fallbacks: bool) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._server_fallbacks = server_fallbacks

    async def complete(self, config: TierConfig, request: CompletionRequest) -> Completion:
        params = dict(
            model=config.model,
            max_tokens=request.max_output_tokens,
            system=request.system,
            messages=[{"role": "user", "content": request.prompt}],
            # Thinking is adaptive by default on current models; effort is the depth knob.
            output_config={"effort": config.effort},
        )
        try:
            if self._server_fallbacks and config.model.startswith(_FALLBACK_MODEL_PREFIXES):
                response = await self._client.beta.messages.create(
                    **params, betas=[_FALLBACK_BETA], fallbacks="default"
                )
            else:
                response = await self._client.messages.create(**params)
        except anthropic.RateLimitError as exc:
            raise LLMRateLimitError("Anthropic rate limit reached. Try again shortly.") from exc
        except anthropic.AuthenticationError as exc:
            raise LLMError("Anthropic rejected the API key.") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Anthropic returned {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Couldn't reach Anthropic.") from exc

        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None)
            raise LLMRefusalError(
                "The model declined this request" + (f" ({category})." if category else ".")
            )
        return Completion(
            text="".join(b.text for b in response.content if b.type == "text"),
            tier=request.tier,
            provider="anthropic",
            # May differ from config.model if a fallback model answered.
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            truncated=response.stop_reason == "max_tokens",
        )

    async def aclose(self) -> None:
        await self._client.close()

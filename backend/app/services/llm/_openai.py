"""OpenAI provider. Private to the llm service."""

import openai

from .types import Completion, CompletionRequest, LLMError, LLMRateLimitError, TierConfig


class _OpenAIProvider:
    def __init__(self, *, api_key: str) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key)

    async def complete(self, config: TierConfig, request: CompletionRequest) -> Completion:
        try:
            response = await self._client.responses.create(
                model=config.model,
                instructions=request.system,
                input=request.prompt,
                max_output_tokens=request.max_output_tokens,
                reasoning={"effort": config.effort},
            )
        except openai.RateLimitError as exc:
            raise LLMRateLimitError("OpenAI rate limit reached. Try again shortly.") from exc
        except openai.AuthenticationError as exc:
            raise LLMError("OpenAI rejected the API key.") from exc
        except openai.APIStatusError as exc:
            raise LLMError(f"OpenAI returned {exc.status_code}: {exc.message}") from exc
        except openai.APIConnectionError as exc:
            raise LLMError("Couldn't reach OpenAI.") from exc

        incomplete = getattr(response.incomplete_details, "reason", None)
        usage = response.usage
        return Completion(
            text=response.output_text,
            tier=request.tier,
            provider="openai",
            model=response.model,
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
            truncated=incomplete == "max_output_tokens",
        )

    async def aclose(self) -> None:
        await self._client.close()

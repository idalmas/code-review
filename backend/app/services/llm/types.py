from typing import Literal

from pydantic import BaseModel, Field

Tier = Literal["cheap", "balanced", "best"]
Provider = Literal["anthropic", "openai"]
Effort = Literal["low", "medium", "high"]


class LLMError(Exception):
    status_code = 502
    code = "llm_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LLMNotConfiguredError(LLMError):
    status_code = 503
    code = "llm_not_configured"


class LLMRateLimitError(LLMError):
    status_code = 429
    code = "llm_rate_limited"


class LLMRefusalError(LLMError):
    """The model declined the request (Anthropic `stop_reason: "refusal"`)."""

    status_code = 422
    code = "llm_refused"


class TierConfig(BaseModel):
    model: str
    effort: Effort


class TierInfo(BaseModel):
    tier: Tier
    label: str
    description: str
    model: str


class LLMStatus(BaseModel):
    enabled: bool
    provider: Provider | None
    default_tier: Tier
    tiers: list[TierInfo]


class CompletionRequest(BaseModel):
    tier: Tier
    system: str
    prompt: str
    max_output_tokens: int = Field(default=4096, gt=0, le=32000)


class Completion(BaseModel):
    text: str
    tier: Tier
    provider: Provider
    model: str
    input_tokens: int
    output_tokens: int
    # True when the model hit max_output_tokens and the text is cut short.
    truncated: bool = False

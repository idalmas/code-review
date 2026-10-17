from types import SimpleNamespace

import pytest

from app.services.llm import (
    CompletionRequest,
    LLMNotConfiguredError,
    LLMRefusalError,
    TierConfig,
    create_llm_service,
)
from app.services.llm._anthropic import _AnthropicProvider  # tests may reach into internals
from app.services.llm._openai import _OpenAIProvider

REQ = CompletionRequest(tier="cheap", system="sys", prompt="hi", max_output_tokens=500)


def test_disabled_without_keys() -> None:
    llm = create_llm_service()
    status = llm.status()
    assert status.enabled is False and status.provider is None and status.tiers == []


async def test_complete_without_keys_raises() -> None:
    with pytest.raises(LLMNotConfiguredError):
        await create_llm_service().complete(REQ)


def test_provider_inferred_from_key_and_tiers_mapped() -> None:
    status = create_llm_service(anthropic_api_key="sk-ant").status()
    assert status.provider == "anthropic"
    assert [(t.tier, t.model) for t in status.tiers] == [
        ("cheap", "claude-haiku-5-5"),
        ("balanced", "claude-sonnet-5-5"),
        ("best", "claude-opus-5-5"),
    ]
    assert create_llm_service(openai_api_key="sk-oa").status().provider == "openai"


def test_explicit_provider_and_overrides() -> None:
    llm = create_llm_service(
        provider="openai",
        anthropic_api_key="sk-ant",
        openai_api_key="sk-oa",
        model_overrides={"best": "my-model"},
    )
    tiers = {t.tier: t.model for t in llm.status().tiers}
    assert llm.status().provider == "openai" and tiers["best"] == "my-model"


def test_explicit_provider_without_its_key_fails_fast() -> None:
    with pytest.raises(LLMNotConfiguredError):
        create_llm_service(provider="openai", anthropic_api_key="sk-ant")


class _Recorder:
    def __init__(self, response) -> None:
        self.response = response
        self.calls: list[dict] = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _anthropic_response(stop_reason="end_turn", model="claude-sonnet-5-5"):
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text="Hello "),
            SimpleNamespace(type="text", text="there"),
        ],
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="cyber") if stop_reason == "refusal" else None,
        model=model,
        usage=SimpleNamespace(input_tokens=10, output_tokens=3),
    )


def _anthropic(monkeypatch, response):
    provider = _AnthropicProvider(api_key="sk-ant", server_fallbacks=True)
    beta, plain = _Recorder(response), _Recorder(response)
    monkeypatch.setattr(provider._client.beta.messages, "create", beta)
    monkeypatch.setattr(provider._client.messages, "create", plain)
    return provider, beta, plain


async def test_anthropic_sonnet_and_opus_use_server_fallbacks(monkeypatch) -> None:
    provider, beta, plain = _anthropic(monkeypatch, _anthropic_response())
    out = await provider.complete(TierConfig(model="claude-sonnet-5-5", effort="medium"), REQ)

    assert out.text == "Hello there" and out.provider == "anthropic"
    assert (out.input_tokens, out.output_tokens, out.truncated) == (10, 3, False)
    assert plain.calls == []
    call = beta.calls[0]
    assert call["fallbacks"] == "default"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["output_config"] == {"effort": "medium"}
    assert call["system"] == "sys" and call["max_tokens"] == 500
    assert "thinking" not in call  # adaptive by default; disabling 400s on current models


async def test_anthropic_haiku_has_no_server_fallback(monkeypatch) -> None:
    provider, beta, plain = _anthropic(monkeypatch, _anthropic_response(model="claude-haiku-5-5"))
    await provider.complete(TierConfig(model="claude-haiku-5-5", effort="low"), REQ)
    assert beta.calls == []
    assert "fallbacks" not in plain.calls[0]


async def test_anthropic_refusal_and_truncation(monkeypatch) -> None:
    provider, *_ = _anthropic(monkeypatch, _anthropic_response(stop_reason="refusal"))
    with pytest.raises(LLMRefusalError, match="cyber"):
        await provider.complete(TierConfig(model="claude-opus-5-5", effort="high"), REQ)

    provider, *_ = _anthropic(monkeypatch, _anthropic_response(stop_reason="max_tokens"))
    out = await provider.complete(TierConfig(model="claude-opus-5-5", effort="high"), REQ)
    assert out.truncated is True


async def test_openai_maps_request_and_response(monkeypatch) -> None:
    provider = _OpenAIProvider(api_key="sk-oa")
    response = SimpleNamespace(
        output_text="Hi",
        model="gpt-5-mini",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        usage=SimpleNamespace(input_tokens=7, output_tokens=2),
    )
    create = _Recorder(response)
    monkeypatch.setattr(provider._client.responses, "create", create)

    out = await provider.complete(TierConfig(model="gpt-5-mini", effort="medium"), REQ)
    assert (out.text, out.provider, out.truncated) == ("Hi", "openai", True)
    assert create.calls[0] == {
        "model": "gpt-5-mini",
        "instructions": "sys",
        "input": "hi",
        "max_output_tokens": 500,
        "reasoning": {"effort": "medium"},
    }

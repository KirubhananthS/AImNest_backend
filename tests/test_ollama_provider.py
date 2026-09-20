"""Focused tests for the Ollama provider abstraction (no network I/O)."""

import json

import httpx
import pytest

from app.core.config import Settings, settings
from app.services.ai import provider_factory
from app.services.ai.ollama_provider import OllamaProvider
from app.services.ai.provider import (
    LLMConnectionError,
    LLMMessage,
    LLMProviderError,
    LLMResponseError,
)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _provider(handler, **overrides) -> OllamaProvider:
    options = {
        "base_url": "http://ollama.test:11434",
        "model": "llama3.2",
        "timeout_seconds": 5.0,
        "max_attempts": 1,
    }
    options.update(overrides)
    return OllamaProvider(client=_client(handler), **options)


def _ok_payload(content: str = "Plan: ship the API.") -> dict:
    return {
        "model": "llama3.2",
        "message": {"role": "assistant", "content": content},
        "done": True,
        "prompt_eval_count": 12,
        "eval_count": 34,
    }


@pytest.fixture(autouse=True)
def _reset_provider_cache():
    provider_factory.reset_provider_cache()
    yield
    provider_factory.reset_provider_cache()


def test_generate_sends_configurable_model_and_parses_reply():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["payload"] = json.loads(request.content.decode())
        return httpx.Response(200, json=_ok_payload("Plan: ship the API."))

    provider = _provider(handler, model="qwen2.5:7b")
    result = provider.generate(
        [LLMMessage(role="user", content="help me plan")],
        temperature=0.1,
        max_output_tokens=128,
    )

    assert captured["url"].endswith("/api/chat")
    assert captured["payload"]["model"] == "qwen2.5:7b"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["messages"] == [{"role": "user", "content": "help me plan"}]
    assert captured["payload"]["options"] == {"temperature": 0.1, "num_predict": 128}

    assert result.content == "Plan: ship the API."
    assert result.provider == "ollama"
    assert result.model == "llama3.2"
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 34
    assert result.latency_ms is not None
    assert result.is_usable is True


def test_generate_requires_at_least_one_message():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no HTTP call expected")

    with pytest.raises(LLMResponseError):
        _provider(handler).generate([])


def test_generate_raises_connection_error_when_server_is_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = _provider(handler)
    with pytest.raises(LLMConnectionError) as exc_info:
        provider.generate([LLMMessage(role="user", content="hi")])

    assert isinstance(exc_info.value, LLMProviderError)


def test_generate_raises_connection_error_on_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(LLMConnectionError):
        _provider(handler).generate([LLMMessage(role="user", content="hi")])


def test_generate_raises_response_error_on_server_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with pytest.raises(LLMResponseError):
        _provider(handler).generate([LLMMessage(role="user", content="hi")])


def test_generate_does_not_retry_client_errors():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(404, json={"error": "model not found"})

    provider = _provider(handler, max_attempts=3, retry_backoff_seconds=0.0)
    with pytest.raises(LLMResponseError):
        provider.generate([LLMMessage(role="user", content="hi")])

    assert calls["count"] == 1


def test_generate_raises_response_error_on_empty_content():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "   "}})

    with pytest.raises(LLMResponseError):
        _provider(handler).generate([LLMMessage(role="user", content="hi")])


def test_generate_raises_response_error_on_non_json_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    with pytest.raises(LLMResponseError):
        _provider(handler).generate([LLMMessage(role="user", content="hi")])


def test_generate_retries_transient_failures_then_succeeds():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json=_ok_payload("Recovered."))

    provider = _provider(handler, max_attempts=3, retry_backoff_seconds=0.0)
    result = provider.generate([LLMMessage(role="user", content="hi")])

    assert calls["count"] == 3
    assert result.content == "Recovered."


def test_health_reports_availability_without_raising():
    def ok(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": []})

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    assert _provider(ok).health() is True
    assert _provider(down).health() is False


def test_settings_read_ollama_values_from_environment(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://env-host:1234")
    monkeypatch.setenv("OLLAMA_MODEL", "phi3:mini")
    monkeypatch.setenv("AI_ENABLED", "false")

    fresh = Settings(_env_file=None)

    assert fresh.ollama_base_url == "http://env-host:1234"
    assert fresh.ollama_model == "phi3:mini"
    assert fresh.ai_enabled is False


def test_provider_factory_builds_provider_from_configuration(monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "ai_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_base_url", "http://custom-host:9999/")
    monkeypatch.setattr(settings, "ollama_model", "mistral:7b")
    provider_factory.reset_provider_cache()

    provider = provider_factory.get_llm_provider()

    assert isinstance(provider, OllamaProvider)
    assert provider.base_url == "http://custom-host:9999"
    assert provider.model == "mistral:7b"


def test_provider_factory_returns_none_when_ai_disabled(monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", False)
    provider_factory.reset_provider_cache()

    assert provider_factory.get_llm_provider() is None


def test_provider_factory_returns_none_for_unknown_provider(monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "ai_provider", "some-hosted-api")
    provider_factory.reset_provider_cache()

    assert provider_factory.get_llm_provider() is None
"""Ollama-backed implementation of the :class:`LLMProvider` contract."""

from __future__ import annotations

import logging
import time
from typing import Any, Sequence

import httpx

from app.services.ai.provider import (
    LLMConnectionError,
    LLMMessage,
    LLMProviderError,
    LLMResponse,
    LLMResponseError,
)

logger = logging.getLogger(__name__)

CHAT_PATH = "/api/chat"
TAGS_PATH = "/api/tags"


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class OllamaProvider:
    """Talks to a local Ollama server over its HTTP API.

    Every transport/HTTP problem is translated into an
    :class:`LLMProviderError` subclass so callers can degrade gracefully
    instead of propagating driver-level exceptions.
    """

    name = "ollama"

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "llama3.2",
        timeout_seconds: float = 30.0,
        keep_alive: str = "5m",
        max_attempts: int = 2,
        retry_backoff_seconds: float = 0.25,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.model = model
        self.timeout_seconds = float(timeout_seconds)
        self.keep_alive = keep_alive
        self.max_attempts = max(1, int(max_attempts))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
        self._client = client
        self._owns_client = client is None

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------
    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout_seconds)
        return self._client

    def close(self) -> None:
        if self._client is not None and self._owns_client:
            self._client.close()
        self._client = None

    # ------------------------------------------------------------------
    # Request plumbing
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, *, json_payload: Any = None) -> httpx.Response:
        url = f"{self.base_url}{path}"
        last_error: LLMProviderError | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.client.request(method, url, json=json_payload)
            except httpx.TimeoutException:
                last_error = LLMConnectionError(
                    f"Ollama request to {url} timed out after {self.timeout_seconds}s"
                )
            except httpx.ConnectError as exc:
                last_error = LLMConnectionError(
                    f"Could not connect to Ollama at {self.base_url}: {exc}"
                )
            except httpx.RequestError as exc:
                last_error = LLMConnectionError(f"Ollama request to {url} failed: {exc}")
            except Exception as exc:  # pragma: no cover - defensive guard
                last_error = LLMConnectionError(f"Unexpected Ollama transport error: {exc}")
            else:
                if response.status_code < 400:
                    return response
                detail = (response.text or "").strip()[:200]
                message = f"Ollama returned HTTP {response.status_code} for {path}: {detail}"
                if 400 <= response.status_code < 500:
                    # Client errors are not worth retrying (e.g. unknown model).
                    raise LLMResponseError(message)
                last_error = LLMResponseError(message)

            if attempt < self.max_attempts:
                logger.warning(
                    "Ollama attempt %s/%s failed (%s)", attempt, self.max_attempts, last_error
                )
                if self.retry_backoff_seconds:
                    time.sleep(self.retry_backoff_seconds)

        raise last_error or LLMConnectionError("Ollama request failed")

    # ------------------------------------------------------------------
    # LLMProvider contract
    # ------------------------------------------------------------------
    def build_payload(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = float(temperature)
        if max_output_tokens is not None:
            options["num_predict"] = int(max_output_tokens)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [message.as_payload() for message in messages],
            "stream": False,
        }
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        if options:
            payload["options"] = options
        return payload

    def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResponse:
        if not messages:
            raise LLMResponseError("Ollama request requires at least one message")

        payload = self.build_payload(
            messages, temperature=temperature, max_output_tokens=max_output_tokens
        )
        started = time.perf_counter()
        response = self._request("POST", CHAT_PATH, json_payload=payload)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return self._parse_chat_response(response, latency_ms)

    def health(self) -> bool:
        try:
            response = self._request("GET", TAGS_PATH)
        except LLMProviderError as exc:
            logger.debug("Ollama health check failed: %s", exc)
            return False
        return response.status_code < 400

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------
    def _parse_chat_response(self, response: httpx.Response, latency_ms: int) -> LLMResponse:
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMResponseError("Ollama returned a non-JSON response") from exc

        if not isinstance(data, dict):
            raise LLMResponseError("Ollama returned an unexpected payload shape")

        if data.get("error"):
            raise LLMResponseError(f"Ollama error: {data['error']}")

        message = data.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not content or not content.strip():
            raise LLMResponseError("Ollama returned an empty assistant message")

        return LLMResponse(
            content=content.strip(),
            provider=self.name,
            model=data.get("model") or self.model,
            prompt_tokens=_as_int(data.get("prompt_eval_count")),
            completion_tokens=_as_int(data.get("eval_count")),
            latency_ms=latency_ms,
        )
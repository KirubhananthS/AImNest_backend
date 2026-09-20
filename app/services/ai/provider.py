"""Provider-agnostic LLM abstraction for the AImNest assistant.

The assistant layer only ever talks to :class:`LLMProvider`, so the concrete
runtime (Ollama today, a hosted API later) can be swapped through configuration
without touching routers or response schemas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, Sequence, runtime_checkable

Role = Literal["system", "user", "assistant"]


class LLMProviderError(RuntimeError):
    """Base class for every provider failure.

    The assistant service treats any subclass as a signal to fall back to the
    deterministic reply, so provider problems never surface as HTTP 5xx.
    """


class LLMConnectionError(LLMProviderError):
    """The provider could not be reached (refused connection, timeout, DNS)."""


class LLMResponseError(LLMProviderError):
    """The provider answered with a non-2xx status or an unusable payload."""


@dataclass(frozen=True)
class LLMMessage:
    """A single chat turn sent to the provider."""

    role: Role
    content: str

    def as_payload(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class LLMResponse:
    """A normalised provider reply plus best-effort usage metadata."""

    content: str
    provider: str | None = None
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: int | None = None

    @property
    def is_usable(self) -> bool:
        return bool(self.content and self.content.strip())


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal contract every LLM runtime must satisfy."""

    name: str

    def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResponse:
        """Return a completion for ``messages`` or raise :class:`LLMProviderError`."""

    def health(self) -> bool:
        """Return ``True`` when the runtime is reachable. Must never raise."""
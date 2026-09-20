"""Ollama integration layer for the AImNest assistant.

Public surface::

    from app.services.ai import get_llm_provider, OllamaProvider, LLMMessage
"""

from app.services.ai.context import (
    AiContext,
    AssistantContextService,
    ContextGoal,
    ContextWorkspace,
)
from app.services.ai.ollama_provider import OllamaProvider
from app.services.ai.prompt_builder import (
    build_chat_messages,
    build_system_prompt,
    render_context,
)
from app.services.ai.provider import (
    LLMConnectionError,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    LLMResponseError,
)
from app.services.ai.provider_factory import (
    create_provider,
    get_llm_provider,
    reset_provider_cache,
)

__all__ = [
    "AiContext",
    "AssistantContextService",
    "ContextGoal",
    "ContextWorkspace",
    "LLMConnectionError",
    "LLMMessage",
    "LLMProvider",
    "LLMProviderError",
    "LLMResponse",
    "LLMResponseError",
    "OllamaProvider",
    "build_chat_messages",
    "build_system_prompt",
    "create_provider",
    "get_llm_provider",
    "render_context",
    "reset_provider_cache",
]
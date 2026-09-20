"""Application boundary for assistant replies.

The deterministic reply produced by :meth:`AssistantService.generate_reply` is
always available and is used whenever the LLM layer is disabled, unreachable or
returns an unusable answer. That keeps the conversation endpoints working
without a local Ollama server and never changes the HTTP response contract.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, cast


from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.db.models.user import User
from app.services.ai import prompt_builder
from app.services.ai.context import AiContext, AssistantContextService
from app.services.ai.provider import LLMMessage, LLMProvider, LLMProviderError, Role

logger = logging.getLogger(__name__)

FALLBACK_TEMPLATE = "AImNest AI: I can help you plan your next step for '{excerpt}'."

# Owned by the prompt builder; re-exported here for backwards compatibility.
SYSTEM_PROMPT = prompt_builder.SYSTEM_PROMPT

CHAT_ROLES = {"system", "user", "assistant"}


@dataclass(frozen=True)
class AssistantReply:
    """Assistant output plus best-effort provider metadata."""

    content: str
    provider: Optional[str] = None
    model: Optional[str] = None
    used_fallback: bool = True
    latency_ms: Optional[int] = None


class AssistantService:
    """Generates assistant replies via a provider, with a safe fallback."""

    def __init__(
        self,
        db: Optional[Session] = None,
        provider: Optional[LLMProvider] = None,
        context_service: Optional[AssistantContextService] = None,
    ):
        # ``db`` is optional and only used to load conversation history and the
        # user-scoped context, which keeps the service unit-testable without a
        # database session.
        self.db = db
        self.provider = provider
        self.context_service = context_service

    @staticmethod
    def generate_reply(user_content: str) -> str:
        """Deterministic reply used when no LLM provider is available."""
        return FALLBACK_TEMPLATE.format(excerpt=user_content[:60])

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    def reply(
        self,
        *,
        content: str,
        user: Optional[User] = None,
        conversation: Optional[Conversation] = None,
    ) -> AssistantReply:
        """Return an assistant reply for ``content``.

        A provider failure is never fatal: the deterministic reply is returned
        so the caller can keep the existing 200 response shape.
        """
        fallback_content = self.generate_reply(content)
        provider = self.provider

        if provider is None:
            return AssistantReply(content=fallback_content)

        messages = self._build_messages(
            content=content,
            user=user,
            conversation=conversation,
            context=self._load_context(user),
        )

        try:
            response = provider.generate(
                messages,
                temperature=settings.ai_temperature,
                max_output_tokens=settings.ai_max_output_tokens,
            )
        except LLMProviderError as exc:
            logger.warning(
                "Assistant provider %r unavailable: %s", getattr(provider, "name", "unknown"), exc
            )
            return AssistantReply(content=fallback_content)
        except Exception:  # pragma: no cover - last-resort guard
            logger.exception("Unexpected assistant provider failure; using deterministic reply")
            return AssistantReply(content=fallback_content)

        if not response.is_usable:
            logger.warning("Assistant provider returned an empty reply; using deterministic reply")
            return AssistantReply(content=fallback_content)

        return AssistantReply(
            content=response.content.strip(),
            provider=response.provider or getattr(provider, "name", None),
            model=response.model,
            used_fallback=False,
            latency_ms=response.latency_ms,
        )

    # ------------------------------------------------------------------
    # Prompt assembly
    # ------------------------------------------------------------------
    def _load_context(self, user: Optional[User]) -> Optional[AiContext]:
        """User-scoped context; a retrieval failure must never break a reply."""
        if user is None or self.db is None or not settings.ai_context_enabled:
            return None
        try:
            service = self.context_service or AssistantContextService(self.db)
            return service.build(user)
        except Exception:  # pragma: no cover - defensive: fall back to no context
            logger.exception("Failed to build assistant context; continuing without it")
            return None

    def _build_messages(
        self,
        *,
        content: str,
        user: Optional[User],
        conversation: Optional[Conversation],
        context: Optional[AiContext] = None,
    ) -> list[LLMMessage]:
        system_content = prompt_builder.build_system_prompt(user, context)
        return prompt_builder.build_chat_messages(
            system_content,
            self._load_history(conversation),
            content,
        )

    def _system_prompt(self, user: Optional[User], context: Optional[AiContext] = None) -> str:
        return prompt_builder.build_system_prompt(user, context)

    def _load_history(self, conversation: Optional[Conversation]) -> list[LLMMessage]:
        limit = max(0, int(settings.ai_history_max_messages))
        if self.db is None or conversation is None or limit == 0:
            return []

        rows = (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
            .all()
        )
        return [
            LLMMessage(role=cast(Role, _normalise_role(row.role)), content=row.content)
            for row in reversed(rows)
        ]


def _normalise_role(role: Optional[str]) -> str:
    normalised = (role or "").strip().lower()
    return normalised if normalised in CHAT_ROLES else "user"

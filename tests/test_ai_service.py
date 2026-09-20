"""Focused tests for AssistantService orchestration and the fallback contract."""

import pytest

from app.core.config import settings
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.db.models.user import User
from app.db.session import SessionLocal
from app.main import app
from app.services.ai.provider import (
    LLMConnectionError,
    LLMMessage,
    LLMResponse,
    LLMResponseError,
)
from app.services.ai.provider_factory import get_llm_provider
from app.services.ai_service import AssistantService

USER_MESSAGE = "Help me plan my next step."


class RecordingProvider:
    """Fake provider capturing the messages it receives."""

    name = "recording"

    def __init__(self, content: str = "Model answer.", error: Exception | None = None):
        self.content = content
        self.error = error
        self.calls: list[dict] = []

    def generate(self, messages, *, temperature=None, max_output_tokens=None) -> LLMResponse:
        self.calls.append(
            {
                "messages": list(messages),
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
            }
        )
        if self.error is not None:
            raise self.error
        return LLMResponse(
            content=self.content,
            provider=self.name,
            model="test-model",
            prompt_tokens=5,
            completion_tokens=7,
            latency_ms=11,
        )

    def health(self) -> bool:
        return True


# ----------------------------------------------------------------------
# Deterministic fallback
# ----------------------------------------------------------------------
def test_deterministic_reply_is_unchanged():
    assert (
        AssistantService.generate_reply(USER_MESSAGE)
        == "AImNest AI: I can help you plan your next step for 'Help me plan my next step.'."
    )
    assert USER_MESSAGE in AssistantService.generate_reply(USER_MESSAGE)


def test_without_provider_uses_deterministic_fallback():
    service = AssistantService(provider=None)

    reply = service.reply(content=USER_MESSAGE)

    assert reply.used_fallback is True
    assert reply.provider is None
    assert reply.model is None
    assert reply.content == AssistantService.generate_reply(USER_MESSAGE)
    assert USER_MESSAGE in reply.content


def test_connection_error_falls_back_safely():
    provider = RecordingProvider(error=LLMConnectionError("connection refused"))
    service = AssistantService(provider=provider)

    reply = service.reply(content=USER_MESSAGE)

    assert reply.used_fallback is True
    assert reply.content == AssistantService.generate_reply(USER_MESSAGE)
    assert len(provider.calls) == 1


def test_unexpected_provider_error_falls_back_safely():
    provider = RecordingProvider(error=RuntimeError("kaboom"))
    service = AssistantService(provider=provider)

    reply = service.reply(content=USER_MESSAGE)

    assert reply.used_fallback is True
    assert reply.content == AssistantService.generate_reply(USER_MESSAGE)


def test_empty_provider_reply_falls_back():
    provider = RecordingProvider(content="   ")
    service = AssistantService(provider=provider)

    reply = service.reply(content=USER_MESSAGE)

    assert reply.used_fallback is True
    assert reply.content == AssistantService.generate_reply(USER_MESSAGE)


def test_provider_reply_is_used_when_usable():
    provider = RecordingProvider(content="Here is your plan.")
    service = AssistantService(provider=provider)

    reply = service.reply(content=USER_MESSAGE)

    assert reply.used_fallback is False
    assert reply.content == "Here is your plan."
    assert reply.provider == "recording"
    assert reply.model == "test-model"
    assert reply.latency_ms == 11


# ----------------------------------------------------------------------
# Prompt assembly
# ----------------------------------------------------------------------
def test_prompt_includes_system_prompt_history_and_current_message(monkeypatch):
    monkeypatch.setattr(settings, "ai_history_max_messages", 4)
    provider = RecordingProvider()
    service = AssistantService(provider=provider)

    service.reply(content="first question")
    service.reply(content="second question")

    sent = provider.calls[-1]["messages"]
    assert sent[0].role == "system"
    assert sent[0].content.startswith("You are AImNest AI")
    assert sent[-1] == LLMMessage(role="user", content="second question")
    assert provider.calls[-1]["temperature"] == settings.ai_temperature
    assert provider.calls[-1]["max_output_tokens"] == settings.ai_max_output_tokens


def test_history_is_bounded_and_current_message_is_excluded(monkeypatch, verified_user_factory, client):
    monkeypatch.setattr(settings, "ai_history_max_messages", 4)

    account = verified_user_factory()
    created = client.post(
        "/api/ai/conversations",
        headers=account["headers"],
        json={"title": "History Bound"},
    )
    assert created.status_code == 200
    conversation_id = created.json()["id"]

    db = SessionLocal()
    try:
        for index in range(15):
            role = "tool" if index == 13 else ("user" if index % 2 == 0 else "assistant")
            db.add(Message(conversation_id=conversation_id, role=role, content=f"history {index}"))
        db.commit()

        provider = RecordingProvider()
        service = AssistantService(db, provider=provider)
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        user = db.query(User).filter(User.id == account["user"]["id"]).first()
        reply = service.reply(content="new question", user=user, conversation=conversation)
    finally:
        db.close()

    assert reply.used_fallback is False
    sent = provider.calls[0]["messages"]
    assert sent[0].role == "system"
    assert account["user"]["name"] in sent[0].content
    assert sent[-1] == LLMMessage(role="user", content="new question")

    history = sent[1:-1]
    assert [message.content for message in history] == [f"history {i}" for i in range(11, 15)]
    assert [message.role for message in history] == ["assistant", "user", "user", "user"]
    # The current turn is appended once and never duplicated from stored history.
    assert [message.content for message in sent].count("new question") == 1


# ----------------------------------------------------------------------
# Endpoint wiring (contract preserved)
# ----------------------------------------------------------------------
def test_conversation_endpoint_uses_injected_provider(verified_user_factory, client):
    account = verified_user_factory()
    created = client.post(
        "/api/ai/conversations",
        headers=account["headers"],
        json={"title": "Ollama Wiring"},
    )
    assert created.status_code == 200
    conversation_id = created.json()["id"]

    provider = RecordingProvider(content="Model generated plan.")
    app.dependency_overrides[get_llm_provider] = lambda: provider

    response = client.post(
        f"/api/ai/conversations/{conversation_id}/messages",
        headers=account["headers"],
        json={"message": "Plan my week"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"]["role"] == "assistant"
    assert body["message"]["content"] == "Model generated plan."
    assert body["role"] == "user"
    assert body["content"] == "Plan my week"
    assert body["conversation"]["id"] == conversation_id
    assert provider.calls, "provider should have been called"

    listing = client.get(
        f"/api/ai/conversations/{conversation_id}/messages", headers=account["headers"]
    )
    assert [item["role"] for item in listing.json()] == ["user", "assistant"]


@pytest.mark.parametrize(
    "error",
    [LLMConnectionError("connection refused"), LLMResponseError("bad payload")],
)
def test_conversation_endpoint_falls_back_when_provider_fails(
    error, verified_user_factory, client
):
    account = verified_user_factory()
    created = client.post(
        "/api/ai/conversations",
        headers=account["headers"],
        json={"title": "Provider Down"},
    )
    conversation_id = created.json()["id"]

    app.dependency_overrides[get_llm_provider] = lambda: RecordingProvider(error=error)

    response = client.post(
        f"/api/ai/conversations/{conversation_id}/messages",
        headers=account["headers"],
        json={"message": "Plan my week"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"]["role"] == "assistant"
    assert body["message"]["content"] == AssistantService.generate_reply("Plan my week")
    assert body["role"] == "user"
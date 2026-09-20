from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user_from_access_token
from app.schemas.conversation import ConversationCreate, ConversationRead
from app.schemas.message import MessageCreate, MessageRead
from app.schemas.assistant import AssistantReplyRead
from app.services.ai.provider import LLMProvider
from app.services.ai.provider_factory import get_llm_provider
from app.services.ai_service import AssistantService

router = APIRouter(prefix="/api/ai/conversations", tags=["conversations"])


def _get_current_user(db: Session, auth_payload: dict) -> User:
    user = db.query(User).filter(User.id == auth_payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _get_owned_conversation(db: Session, conversation_id: str, user: User) -> Conversation:
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == user.id,
    ).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post("", response_model=ConversationRead)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Conversation title must not be empty")
    conversation = Conversation(user_id=user.id, title=title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("", response_model=list[ConversationRead])
def list_conversations(
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    return db.query(Conversation).filter(
        Conversation.user_id == user.id,
    ).order_by(Conversation.updated_at.desc()).all()


@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    return _get_owned_conversation(db, conversation_id, user)


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    conversation = _get_owned_conversation(db, conversation_id, user)
    db.delete(conversation)
    db.commit()
    return {"message": "Conversation deleted"}


def _message_response(message: Message) -> dict:
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at,
        "sender": message.role,
        "body": message.content,
        "createdAt": message.created_at,
    }


@router.post("/{conversation_id}/messages", response_model=AssistantReplyRead)
def create_message(
    conversation_id: str,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
    provider: LLMProvider | None = Depends(get_llm_provider),
):
    user = _get_current_user(db, auth_payload)
    conversation = _get_owned_conversation(db, conversation_id, user)
    try:
        content = payload.message_content()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user_message = Message(conversation_id=conversation.id, role="user", content=content)
    reply = AssistantService(db, provider=provider).reply(
        content=content,
        user=user,
        conversation=conversation,
    )
    assistant_message = Message(conversation_id=conversation.id, role="assistant", content=reply.content)
    db.add(user_message)
    db.add(assistant_message)
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)
    return {
        **_message_response(user_message),
        "message": _message_response(assistant_message),
        "conversation": {
            "id": conversation.id,
            "user_id": conversation.user_id,
            "title": conversation.title,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
        },
    }


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    conversation = _get_owned_conversation(db, conversation_id, user)
    messages = db.query(Message).filter(
        Message.conversation_id == conversation.id,
    ).order_by(Message.created_at.asc()).all()
    return [_message_response(message) for message in messages]

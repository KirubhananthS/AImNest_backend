from typing import Any

from pydantic import BaseModel

from app.schemas.conversation import ConversationRead
from app.schemas.message import MessageRead


class AssistantReplyRead(BaseModel):
    message: MessageRead
    conversation: ConversationRead
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: Any
    sender: str
    body: str
    createdAt: Any

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    role: str = Field(default="user", min_length=1, max_length=30)
    message: Optional[str] = Field(default=None, min_length=1, max_length=20000)
    content: Optional[str] = Field(default=None, min_length=1, max_length=20000)
    body: Optional[str] = Field(default=None, min_length=1, max_length=20000)

    def message_content(self) -> str:
        content = self.message or self.content or self.body
        if content is None or not content.strip():
            raise ValueError("Message content must not be empty")
        return content.strip()


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime
    sender: Optional[str] = None
    body: Optional[str] = None
    createdAt: Optional[datetime] = None

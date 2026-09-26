from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TicketBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=100)
    difficulty: str = Field(default="beginner", max_length=50)
    priority: str = Field(default="medium", max_length=50)
    status: str = Field(default="open", max_length=50)
    goal_id: Optional[str] = None


class TicketCreate(TicketBase):
    pass


class TicketUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, min_length=1)
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    difficulty: Optional[str] = Field(default=None, max_length=50)
    priority: Optional[str] = Field(default=None, max_length=50)
    status: Optional[str] = Field(default=None, max_length=50)
    goal_id: Optional[str] = None


class TicketRead(TicketBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    assigned_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
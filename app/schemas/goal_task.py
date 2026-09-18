from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GoalTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    status: str = Field(default="pending", min_length=1, max_length=30)
    due_date: Optional[datetime] = None


class GoalTaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    status: Optional[str] = Field(default=None, min_length=1, max_length=30)
    due_date: Optional[datetime] = None


class GoalTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    goal_id: str
    title: str
    description: Optional[str] = None
    status: str
    due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

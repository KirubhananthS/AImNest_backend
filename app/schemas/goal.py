from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    category: str = Field(min_length=1, max_length=80)
    priority: str = Field(min_length=1, max_length=30)
    deadline: date
    status: str = Field(default="active", min_length=1, max_length=30)
    progress: int = Field(default=0, ge=0, le=100)
    completed: bool = False


class GoalUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, min_length=1, max_length=5000)
    category: Optional[str] = Field(default=None, min_length=1, max_length=80)
    priority: Optional[str] = Field(default=None, min_length=1, max_length=30)
    deadline: Optional[date] = None
    status: Optional[str] = Field(default=None, min_length=1, max_length=30)
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    completed: Optional[bool] = None


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    description: str
    category: str
    priority: str
    deadline: date
    status: str
    progress: int
    completed: bool
    created_at: datetime
    updated_at: datetime

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    status: str = Field(default="pending", min_length=1, max_length=30)
    priority: str = Field(default="medium", min_length=1, max_length=30)
    due_date: Optional[datetime] = None


class WorkspaceTaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    status: Optional[str] = Field(default=None, min_length=1, max_length=30)
    priority: Optional[str] = Field(default=None, min_length=1, max_length=30)
    due_date: Optional[datetime] = None


class WorkspaceTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

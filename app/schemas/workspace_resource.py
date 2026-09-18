from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceResourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    size: Optional[str] = Field(default=None, max_length=50)
    type: str = Field(min_length=1, max_length=30)
    icon: Optional[str] = Field(default=None, max_length=80)
    color: Optional[str] = Field(default=None, max_length=30)


class WorkspaceResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    name: str
    size: Optional[str] = None
    type: str
    icon: Optional[str] = None
    color: Optional[str] = None
    created_at: datetime
    updated_at: datetime

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkspaceMemberCreate(BaseModel):
    user_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    email: Optional[str] = Field(default=None, min_length=3, max_length=255)
    role: str = Field(default="member", min_length=1, max_length=50)

    @model_validator(mode="after")
    def require_user_reference(self):
        if not self.user_id and not self.email:
            raise ValueError("user_id or email is required")
        return self


class WorkspaceMemberRoleUpdate(BaseModel):
    role: str = Field(min_length=1, max_length=50)


class WorkspaceMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    user_id: str
    role: str
    created_at: datetime
    user_name: Optional[str] = None
    user_email: Optional[str] = None

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    user_id: Optional[str] = None
    action: str
    description: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime
    title: Optional[str] = None
    subtitle: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None

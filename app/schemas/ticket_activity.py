from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class TicketActivityRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    id: str
    ticket_id: str
    user_id: Optional[str] = None
    action: str
    description: Optional[str] = None

    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        validation_alias="event_metadata",
        serialization_alias="metadata",
    )

    created_at: datetime
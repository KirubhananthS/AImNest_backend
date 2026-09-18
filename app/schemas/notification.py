from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    body: str
    read: bool = Field(validation_alias="is_read", serialization_alias="read")
    created_at: datetime

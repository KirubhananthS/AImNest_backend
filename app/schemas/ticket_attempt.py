from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TicketAttemptBase(BaseModel):
    solution: str = Field(min_length=1)
    evidence: Optional[str] = None


class TicketAttemptCreate(TicketAttemptBase):
    pass


class TicketAttemptRead(TicketAttemptBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ticket_id: str
    user_id: str
    attempt_number: int
    status: str
    submitted_at: datetime
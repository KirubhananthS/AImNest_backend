from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TicketEvaluationBase(BaseModel):
    is_correct: bool = False
    score: float = Field(default=0.0, ge=0.0, le=100.0)
    feedback: str = Field(min_length=1)
    root_cause_quality: Optional[int] = Field(default=None, ge=0, le=10)
    solution_quality: Optional[int] = Field(default=None, ge=0, le=10)
    evidence_quality: Optional[int] = Field(default=None, ge=0, le=10)
    next_action: Optional[str] = Field(default=None, max_length=100)


class TicketEvaluationRead(TicketEvaluationBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    attempt_id: str
    created_at: datetime
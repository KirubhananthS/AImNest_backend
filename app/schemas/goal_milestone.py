from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GoalMilestoneCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    status: str = Field(default="pending", min_length=1, max_length=30)


class GoalMilestoneUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    status: Optional[str] = Field(default=None, min_length=1, max_length=30)


class GoalMilestoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    goal_id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime

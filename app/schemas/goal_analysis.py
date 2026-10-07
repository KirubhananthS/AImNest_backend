from typing import Optional

from pydantic import BaseModel, Field


class GoalAnalysisTopic(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=1000)
    priority: str = Field(default="medium", max_length=30)


class GoalAnalysisResponse(BaseModel):
    goal_id: str

    summary: str = Field(min_length=1, max_length=3000)

    learner_level: str = Field(
        min_length=1,
        max_length=50,
    )

    skill_gaps: list[str] = Field(
        default_factory=list,
    )

    topics: list[GoalAnalysisTopic] = Field(
        default_factory=list,
    )

    recommended_difficulty: str = Field(
        default="beginner",
        max_length=50,
    )

    learning_sequence: list[str] = Field(
        default_factory=list,
    )

    expectations: Optional[str] = Field(
        default=None,
        max_length=3000,
    )

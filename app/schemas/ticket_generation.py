from pydantic import BaseModel, Field


class GeneratedTicketAcceptanceCriteria(BaseModel):
    criterion: str = Field(
        min_length=1,
        max_length=500,
    )
def _get_skill_difficulty(
    self,
    skill: str,
    learner_skills: list[LearnerSkill],
) -> str:
    normalized_skill = skill.strip().lower()

    for learner_skill in learner_skills:
        if learner_skill.skill.strip().lower() == normalized_skill:
            return learner_skill.level

    return "beginner"


class GeneratedTicket(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=200,
    )

    description: str = Field(
        min_length=1,
        max_length=3000,
    )

    objective: str = Field(
        min_length=1,
        max_length=2000,
    )

    difficulty: str = Field(
        default="beginner",
        max_length=30,
    )

    skill: str = Field(
        min_length=1,
        max_length=120,
    )

    expected_outcome: str = Field(
        min_length=1,
        max_length=2000,
    )

    acceptance_criteria: list[
        GeneratedTicketAcceptanceCriteria
    ] = Field(
        default_factory=list,
    )


class TicketGenerationResponse(BaseModel):
    goal_id: str

    learner_level: str = Field(
        min_length=1,
        max_length=50,
    )

    recommended_difficulty: str = Field(
        min_length=1,
        max_length=50,
    )

    tickets: list[GeneratedTicket] = Field(
        default_factory=list,
    )
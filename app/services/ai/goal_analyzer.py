from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.goal import Goal
from app.db.models.user import User
from app.schemas.goal_analysis import GoalAnalysisResponse
from app.services.ai import get_llm_provider, LLMMessage
from app.services.learner_skill_service import LearnerSkillService


class GoalAnalyzer:
    def __init__(self, db: Session):
        self.db = db
        self.provider = get_llm_provider()
        self.learner_skill_service = LearnerSkillService(db)

    def analyze(
        self,
        goal: Goal,
        user: User,
    ) -> GoalAnalysisResponse:
        prompt = self._build_prompt(goal, user)

        response = self.provider.generate(
            messages=[
                LLMMessage(
                    role="system",
                    content=self._system_prompt(),
                ),
                LLMMessage(
                    role="user",
                    content=prompt,
                ),
            ]
        )

        data = self._parse_response(response.content)

        data["goal_id"] = goal.id

        skill_gaps = data.get("skill_gaps", [])

        if isinstance(skill_gaps, list):
            self.learner_skill_service.create_initial_skills(
                user_id=user.id,
                skills=skill_gaps,
                level=self._normalize_skill_level(
                    data.get("learner_level")
                ),
            )

        return GoalAnalysisResponse.model_validate(data)

    def _normalize_skill_level(
        self,
        level: Any,
    ) -> str:
        if not isinstance(level, str):
            return "beginner"

        normalized = level.strip().lower()

        allowed_levels = {
            "beginner",
            "intermediate",
            "advanced",
        }

        if normalized not in allowed_levels:
            return "beginner"

        return normalized

    def _system_prompt(self) -> str:
        return """
You are the AImNest Goal Analysis Engine.

Your job is to analyze a learner's goal and create a
personalized learning analysis.

Use ONLY the information provided about the learner and goal.

Analyze:

1. The learner's current level.
2. The learner's experience.
3. The learner's expectations.
4. The skills required for the goal.
5. The likely skill gaps.
6. The topics the learner should study.
7. A logical learning sequence.
8. The appropriate difficulty.

Do not create study links yet.
Do not create tickets yet.
Do not invent certifications, experience, or knowledge
that the learner did not provide.

Return ONLY valid JSON.

JSON structure:

{
  "summary": "short analysis",
  "learner_level": "beginner/intermediate/advanced",
  "skill_gaps": ["topic 1", "topic 2"],
  "topics": [
    {
      "title": "topic",
      "reason": "why this topic is needed",
      "priority": "high/medium/low"
    }
  ],
  "recommended_difficulty": "beginner/intermediate/advanced",
  "learning_sequence": [
    "topic 1",
    "topic 2"
  ],
  "expectations": "learner expectations"
}
""".strip()

    def _build_prompt(
        self,
        goal: Goal,
        user: User,
    ) -> str:
        return f"""
LEARNER

Name: {user.name}
Level: {user.level or "Not specified"}
Bio / Experience: {user.bio or "Not specified"}

GOAL

Title: {goal.title}
Description: {goal.description}
Category: {goal.category}
Priority: {goal.priority}
Deadline: {goal.deadline}
Current Progress: {goal.progress}%

Analyze this learner's goal and produce a personalized
learning analysis.
""".strip()

    def _parse_response(
        self,
        content: str,
    ) -> dict[str, Any]:
        content = content.strip()

        if content.startswith("```"):
            content = (
                content
                .removeprefix("```json")
                .removeprefix("```")
            )
            content = content.removesuffix("```").strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "AI returned an invalid goal analysis response"
            ) from exc

        if not isinstance(data, dict):
            raise ValueError(
                "AI goal analysis response must be a JSON object"
            )

        return data
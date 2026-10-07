from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.learner_skill import LearnerSkill
from app.db.models.ticket_attempt import TicketAttempt
from app.db.models.ticket_evaluation import TicketEvaluation
from app.db.models.user import User
from app.schemas.ticket_evaluation import TicketEvaluationRead
from app.services.ai import LLMMessage, get_llm_provider
from app.services.learner_skill_service import LearnerSkillService


class TicketEvaluator:
    def __init__(self, db: Session):
        self.db = db
        self.provider = get_llm_provider()

    def evaluate(
        self,
        attempt: TicketAttempt,
        user: User,
    ) -> TicketEvaluationRead:
        if not attempt.ticket:
            raise ValueError("Ticket not found for this attempt")

        ticket = attempt.ticket

        learner_skills = (
            self.db.query(LearnerSkill)
            .filter(
                LearnerSkill.user_id == user.id
            )
            .order_by(LearnerSkill.skill.asc())
            .all()
        )

        prompt = self._build_prompt(
            attempt=attempt,
            user=user,
            learner_skills=learner_skills,
        )

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

        evaluation = TicketEvaluation(
            attempt_id=attempt.id,
            is_correct=data["is_correct"],
            score=data["score"],
            feedback=data["feedback"],
            root_cause_quality=data.get(
                "root_cause_quality"
            ),
            solution_quality=data.get(
                "solution_quality"
            ),
            evidence_quality=data.get(
                "evidence_quality"
            ),
            next_action=data.get(
                "next_action"
            ),
        )

        self.db.add(evaluation)
        self.db.commit()
        self.db.refresh(evaluation)

        # Update learner skill after successful evaluation.
        skill_service = LearnerSkillService(self.db)

        skill_service.update_from_evaluation(
            user_id=user.id,
            skill=ticket.category,
            score=evaluation.score,
            root_cause_quality=evaluation.root_cause_quality,
            solution_quality=evaluation.solution_quality,
            evidence_quality=evaluation.evidence_quality,
        )

        return TicketEvaluationRead.model_validate(
            evaluation
        )

    def _system_prompt(self) -> str:
        return """
You are the AImNest Ticket Evaluation Engine.

Your job is to evaluate a learner's submitted solution
for a practical learning ticket.

Evaluate ONLY using the information provided.

Consider:

1. Whether the learner completed the requested task.
2. Whether the solution is technically correct.
3. Whether the learner demonstrates understanding.
4. Whether the provided evidence supports the solution.
5. The quality of the root-cause explanation when relevant.
6. The quality of the proposed solution.
7. Whether the next learning action is appropriate.

Scoring:

score:
0 to 100

root_cause_quality:
0 to 10

solution_quality:
0 to 10

evidence_quality:
0 to 10

Rules:

1. Do not assume work was completed if evidence is missing.
2. Do not invent evidence.
3. Do not give full credit for an unsupported claim.
4. Be constructive and specific.
5. Evaluate according to the learner's current level.
6. Do not judge the learner personally.
7. Do not create a new ticket.
8. Do not modify learner skills directly.
9. Return ONLY valid JSON.

JSON structure:

{
  "is_correct": true,
  "score": 0,
  "feedback": "specific feedback",
  "root_cause_quality": 0,
  "solution_quality": 0,
  "evidence_quality": 0,
  "next_action": "short next learning action"
}
""".strip()

    def _build_prompt(
        self,
        attempt: TicketAttempt,
        user: User,
        learner_skills: list[LearnerSkill],
    ) -> str:
        ticket = attempt.ticket

        skills_text = self._format_skills(
            learner_skills
        )

        return f"""
LEARNER

Name:
{user.name}

Level:
{user.level or "Not specified"}

Bio / Experience:
{user.bio or "Not specified"}

CURRENT LEARNER SKILLS

{skills_text}

TICKET

Title:
{ticket.title}

Description:
{ticket.description}

Category:
{ticket.category}

Difficulty:
{ticket.difficulty}

Priority:
{ticket.priority}

EXPECTED TICKET STATUS:
{ticket.status}

LEARNER ATTEMPT

Attempt Number:
{attempt.attempt_number}

Solution:
{attempt.solution}

Evidence:
{attempt.evidence or "No evidence provided"}

Evaluate this learner attempt against the ticket requirements.
""".strip()

    def _format_skills(
        self,
        learner_skills: list[LearnerSkill],
    ) -> str:
        if not learner_skills:
            return "No learner skills recorded yet."

        lines: list[str] = []

        for skill in learner_skills:
            lines.append(
                f"- {skill.skill}: "
                f"level={skill.level}, "
                f"experience_score={skill.experience_score}, "
                f"confidence_score={skill.confidence_score}, "
                f"evidence_count={skill.evidence_count}"
            )

        return "\n".join(lines)

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
            content = (
                content
                .removesuffix("```")
                .strip()
            )

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "AI returned an invalid ticket evaluation response"
            ) from exc

        if not isinstance(data, dict):
            raise ValueError(
                "AI ticket evaluation response must be a JSON object"
            )

        self._validate_response(data)

        return data

    def _validate_response(
        self,
        data: dict[str, Any],
    ) -> None:
        required_fields = {
            "is_correct",
            "score",
            "feedback",
        }

        missing_fields = (
            required_fields - data.keys()
        )

        if missing_fields:
            raise ValueError(
                "AI ticket evaluation response "
                f"is missing fields: "
                f"{', '.join(sorted(missing_fields))}"
            )

        if not isinstance(
            data["is_correct"],
            bool,
        ):
            raise ValueError(
                "AI evaluation is_correct must be boolean"
            )

        score = data["score"]

        if not isinstance(
            score,
            (int, float),
        ):
            raise ValueError(
                "AI evaluation score must be numeric"
            )

        if not 0 <= float(score) <= 100:
            raise ValueError(
                "AI evaluation score must be between 0 and 100"
            )

        for field in (
            "root_cause_quality",
            "solution_quality",
            "evidence_quality",
        ):
            value = data.get(field)

            if value is None:
                continue

            if not isinstance(value, int):
                raise ValueError(
                    f"AI evaluation {field} must be an integer"
                )

            if not 0 <= value <= 10:
                raise ValueError(
                    f"AI evaluation {field} "
                    "must be between 0 and 10"
                )

        if not isinstance(
            data["feedback"],
            str,
        ) or not data["feedback"].strip():
            raise ValueError(
                "AI evaluation feedback cannot be empty"
            )

        next_action = data.get("next_action")

        if next_action is not None:
            if not isinstance(
                next_action,
                str,
            ):
                raise ValueError(
                    "AI evaluation next_action must be a string"
                )
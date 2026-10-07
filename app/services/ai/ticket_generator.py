from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.goal import Goal
from app.db.models.learner_skill import LearnerSkill
from app.db.models.ticket import Ticket
from app.db.models.ticket_activity import TicketActivity
from app.db.models.user import User
from app.schemas.goal_analysis import GoalAnalysisResponse
from app.schemas.ticket_generation import TicketGenerationResponse
from app.services.ai import LLMMessage, get_llm_provider


class TicketGenerator:
    def __init__(self, db: Session):
        self.db = db
        self.provider = get_llm_provider()

    def _get_skill_difficulty(
        self,
        skill: str,
        learner_skills: list[LearnerSkill],
    ) -> str:
        normalized_skill = skill.strip().lower()

        for learner_skill in learner_skills:
            if (
                learner_skill.skill.strip().lower()
                == normalized_skill
            ):
                return learner_skill.level

        return "beginner"

    def _ticket_exists(
        self,
        user_id: str,
        goal_id: str,
        title: str,
        skill: str,
    ) -> bool:
        normalized_title = title.strip().lower()
        normalized_skill = skill.strip().lower()

        existing_ticket = (
            self.db.query(Ticket.id)
            .filter(
                Ticket.user_id == user_id,
                Ticket.goal_id == goal_id,
                func.lower(Ticket.title)
                == normalized_title,
                func.lower(Ticket.category)
                == normalized_skill,
            )
            .first()
        )

        return existing_ticket is not None

    def generate(
        self,
        goal: Goal,
        user: User,
        goal_analysis: GoalAnalysisResponse,
    ) -> TicketGenerationResponse:
        learner_skills = (
            self.db.query(LearnerSkill)
            .filter(
                LearnerSkill.user_id == user.id
            )
            .order_by(
                LearnerSkill.skill.asc()
            )
            .all()
        )

        prompt = self._build_prompt(
            goal=goal,
            user=user,
            goal_analysis=goal_analysis,
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

        data = self._parse_response(
            response.content
        )

        data["goal_id"] = goal.id

        # Backend-level adaptive difficulty.
        # The learner's stored skill level takes priority
        # over whatever difficulty the AI returns.
        for ticket in data.get("tickets", []):
            skill = ticket.get("skill", "")

            ticket["difficulty"] = (
                self._get_skill_difficulty(
                    skill=skill,
                    learner_skills=learner_skills,
                )
            )

        if "learner_level" not in data:
            data["learner_level"] = (
                goal_analysis.learner_level
            )

        if "recommended_difficulty" not in data:
            data["recommended_difficulty"] = (
                goal_analysis.recommended_difficulty
            )

        return TicketGenerationResponse.model_validate(
            data
        )

    def generate_and_save(
        self,
        goal: Goal,
        user: User,
        goal_analysis: GoalAnalysisResponse,
    ) -> TicketGenerationResponse:
        result = self.generate(
            goal=goal,
            user=user,
            goal_analysis=goal_analysis,
        )

        created_tickets: list[Ticket] = []

        try:
            for generated_ticket in result.tickets:

                # Prevent duplicate tickets for the same
                # user + goal + skill + title.
                if self._ticket_exists(
                    user_id=user.id,
                    goal_id=goal.id,
                    title=generated_ticket.title,
                    skill=generated_ticket.skill,
                ):
                    continue

                ticket = Ticket(
                    user_id=user.id,
                    goal_id=goal.id,
                    title=generated_ticket.title.strip(),
                    description=(
                        generated_ticket.description.strip()
                    ),
                    category=generated_ticket.skill.strip(),
                    difficulty=generated_ticket.difficulty,
                    priority=goal.priority or "medium",
                    status="open",
                    progress=0,
                    due_date=None,
                )

                self.db.add(ticket)

                # Generate ticket.id before creating activity.
                self.db.flush()

                activity = TicketActivity(
                    ticket_id=ticket.id,
                    user_id=user.id,
                    action="ticket_created",
                    description=(
                        f"Ticket created by AI: "
                        f"{ticket.title}"
                    ),
                    event_metadata={
                        "source": "ai_ticket_generator",
                        "goal_id": goal.id,
                        "skill": generated_ticket.skill,
                        "difficulty": (
                            generated_ticket.difficulty
                        ),
                    },
                )

                self.db.add(activity)

                created_tickets.append(ticket)

            self.db.commit()

            for ticket in created_tickets:
                self.db.refresh(ticket)

            return result

        except Exception:
            self.db.rollback()
            raise

    def _system_prompt(self) -> str:
        return """
You are the AImNest Adaptive Ticket Generator.

Your job is to create practical learning tickets
for a learner based on their goal, goal analysis,
current learner skills, experience, and confidence.

Use ONLY the information provided.

Rules:

1. Create practical and actionable learning tasks.
2. Match the difficulty to the learner's current level.
3. Focus on one primary skill per ticket.
4. Prefer hands-on tasks over theoretical questions.
5. Do not assume knowledge that is not provided.
6. Do not create study links.
7. Do not evaluate the learner.
8. Do not create certifications.
9. Keep the ticket achievable for the learner's level.
10. Include clear acceptance criteria.

Return ONLY valid JSON.

JSON structure:

{
  "learner_level": "beginner/intermediate/advanced",
  "recommended_difficulty": "beginner/intermediate/advanced",
  "tickets": [
    {
      "title": "short practical task title",
      "description": "what the learner needs to do",
      "objective": "what the learner should learn",
      "difficulty": "beginner/intermediate/advanced",
      "skill": "primary skill",
      "expected_outcome": "what successful completion looks like",
      "acceptance_criteria": [
        {
          "criterion": "specific condition"
        }
      ]
    }
  ]
}

Generate 1 to 3 tickets only.
""".strip()

    def _build_prompt(
        self,
        goal: Goal,
        user: User,
        goal_analysis: GoalAnalysisResponse,
        learner_skills: list[LearnerSkill],
    ) -> str:
        skills_text = self._format_skills(
            learner_skills
        )

        skill_gaps_text = ", ".join(
            goal_analysis.skill_gaps
        )

        sequence_text = ", ".join(
            goal_analysis.learning_sequence
        )

        return f"""
LEARNER

Name: {user.name}
Level: {user.level or "Not specified"}
Bio / Experience: {user.bio or "Not specified"}

CURRENT LEARNER SKILLS

{skills_text}

ADAPTIVE LEARNING RULES

1. Match each ticket's difficulty to the current level of its primary skill.
2. For beginner skills, create beginner-level practical tasks.
3. For intermediate skills, create intermediate-level practical tasks.
4. For advanced skills, create advanced-level practical tasks.
5. Prefer skills with lower confidence_score or lower experience_score.
6. If a skill already has strong evidence_count and high confidence_score,
   make the next task slightly more challenging.
7. Avoid repeatedly generating the same task type for a skill that already
   has strong evidence.
8. Use the learner's current skill data as the primary signal for adaptive difficulty.

GOAL

Title: {goal.title}
Description: {goal.description}
Category: {goal.category}
Priority: {goal.priority}
Progress: {goal.progress}%

GOAL ANALYSIS

Summary:
{goal_analysis.summary}

Learner Level:
{goal_analysis.learner_level}

Skill Gaps:
{skill_gaps_text}

Recommended Difficulty:
{goal_analysis.recommended_difficulty}

Learning Sequence:
{sequence_text}

Expectations:
{goal_analysis.expectations or "Not specified"}

Create practical learning tickets for this learner.
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
                (
                    f"- {skill.skill}: "
                    f"level={skill.level}, "
                    f"experience_score={skill.experience_score}, "
                    f"confidence_score={skill.confidence_score}, "
                    f"evidence_count={skill.evidence_count}"
                )
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
                "AI returned an invalid ticket generation response"
            ) from exc

        if not isinstance(data, dict):
            raise ValueError(
                "AI ticket generation response must be a JSON object"
            )

        return data
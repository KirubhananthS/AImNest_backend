from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.learner_skill import LearnerSkill


class LearnerSkillService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_skills(
        self,
        user_id: str,
    ) -> list[LearnerSkill]:
        return (
            self.db.query(LearnerSkill)
            .filter(LearnerSkill.user_id == user_id)
            .order_by(LearnerSkill.skill.asc())
            .all()
        )

    def get_skill(
        self,
        user_id: str,
        skill: str,
    ) -> Optional[LearnerSkill]:
        normalized_skill = skill.strip()

        if not normalized_skill:
            return None

        return (
            self.db.query(LearnerSkill)
            .filter(
                LearnerSkill.user_id == user_id,
                LearnerSkill.skill == normalized_skill,
            )
            .first()
        )

    def create_or_update_skill(
        self,
        user_id: str,
        skill: str,
        level: str = "beginner",
        experience_score: float = 0.0,
        confidence_score: float = 0.0,
        evidence_count: int = 0,
    ) -> LearnerSkill:
        normalized_skill = skill.strip()

        if not normalized_skill:
            raise ValueError("Skill cannot be empty")

        existing = self.get_skill(
            user_id=user_id,
            skill=normalized_skill,
        )

        if existing:
            existing.level = level
            existing.experience_score = experience_score
            existing.confidence_score = confidence_score
            existing.evidence_count = evidence_count
            existing.updated_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(existing)

            return existing

        learner_skill = LearnerSkill(
            user_id=user_id,
            skill=normalized_skill,
            level=level,
            experience_score=experience_score,
            confidence_score=confidence_score,
            evidence_count=evidence_count,
            last_evaluated_at=None,
        )

        self.db.add(learner_skill)
        self.db.commit()
        self.db.refresh(learner_skill)

        return learner_skill

    def update_from_evaluation(
        self,
        user_id: str,
        skill: str,
        score: float,
        root_cause_quality: Optional[int] = None,
        solution_quality: Optional[int] = None,
        evidence_quality: Optional[int] = None,
    ) -> LearnerSkill:
        normalized_skill = skill.strip()

        if not normalized_skill:
            raise ValueError("Skill cannot be empty")

        if score < 0 or score > 100:
            raise ValueError("Score must be between 0 and 100")

        existing = self.get_skill(
            user_id=user_id,
            skill=normalized_skill,
        )

        if not existing:
            existing = LearnerSkill(
                user_id=user_id,
                skill=normalized_skill,
                level="beginner",
                experience_score=0.0,
                confidence_score=0.0,
                evidence_count=0,
                last_evaluated_at=None,
            )
            self.db.add(existing)
            self.db.flush()

        quality_values = [
            value
            for value in (
                root_cause_quality,
                solution_quality,
                evidence_quality,
            )
            if value is not None
        ]

        if quality_values:
            quality_score = (
                sum(quality_values) / len(quality_values)
            ) * 10.0
        else:
            quality_score = score

        confidence_score = (
            (score * 0.7)
            + (quality_score * 0.3)
        )

        existing.confidence_score = round(
            max(0.0, min(100.0, confidence_score)),
            2,
        )

        experience_gain = 5.0 + (score * 0.05)

        existing.experience_score = round(
            min(
                100.0,
                existing.experience_score + experience_gain,
            ),
            2,
        )

        existing.evidence_count += 1

        if existing.confidence_score >= 80:
            existing.level = "advanced"
        elif existing.confidence_score >= 50:
            existing.level = "intermediate"
        else:
            existing.level = "beginner"

        existing.last_evaluated_at = datetime.now(timezone.utc)
        existing.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(existing)

        return existing

    def create_initial_skills(
        self,
        user_id: str,
        skills: list[str],
        level: str = "beginner",
        commit: bool = True,
    ) -> list[LearnerSkill]:
        created_skills: list[LearnerSkill] = []

        for skill in skills:
            normalized_skill = skill.strip()

            if not normalized_skill:
                continue

            existing = self.get_skill(
                user_id=user_id,
                skill=normalized_skill,
            )

            if existing:
                created_skills.append(existing)
                continue

            learner_skill = LearnerSkill(
                user_id=user_id,
                skill=normalized_skill,
                level=level,
                experience_score=0.0,
                confidence_score=0.0,
                evidence_count=0,
                last_evaluated_at=None,
            )

            self.db.add(learner_skill)
            created_skills.append(learner_skill)

        if commit:
            self.db.commit()

            for learner_skill in created_skills:
                self.db.refresh(learner_skill)

        return created_skills

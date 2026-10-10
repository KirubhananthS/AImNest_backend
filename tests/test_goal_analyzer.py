import json
from datetime import date

import pytest

from app.db.models.goal import Goal
from app.db.models.goal_analysis import GoalAnalysis
from app.db.models.learner_skill import LearnerSkill
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services.ai.provider import LLMResponse
from app.services.ai.goal_analyzer import GoalAnalyzer


class FakeGoalProvider:
    def __init__(self, content: str):
        self.content = content

    def generate(self, messages, **kwargs):
        return LLMResponse(
            content=self.content,
            provider="test",
            model="test-model",
            prompt_tokens=1,
            completion_tokens=1,
            latency_ms=1,
        )


def valid_analysis():
    return {
        "summary": "A practical learning plan.",
        "learner_level": "beginner",
        "skill_gaps": ["Kubernetes", "Linux"],
        "topics": [
            {
                "title": "Kubernetes basics",
                "reason": "Understand core concepts",
                "priority": "high",
            }
        ],
        "recommended_difficulty": "beginner",
        "learning_sequence": ["Linux", "Kubernetes"],
        "expectations": "Deploy an application",
    }


@pytest.fixture
def goal_context(verified_user_factory):
    account = verified_user_factory()
    db = SessionLocal()
    user = None
    goal = None

    try:
        user = db.query(User).filter(
            User.id == account["user"]["id"]
        ).one()

        goal = Goal(
            user_id=user.id,
            title="Learn Kubernetes",
            description="Deploy and troubleshoot applications",
            category="technology",
            priority="high",
            deadline=date(2027, 1, 1),
            status="active",
            progress=0,
            completed=False,
        )
        db.add(goal)
        db.commit()
        db.refresh(goal)

        yield db, goal, user

    finally:
        if user is not None:
            if goal is not None:
                db.query(GoalAnalysis).filter(
                    GoalAnalysis.goal_id == goal.id
                ).delete(synchronize_session=False)

                db.query(Goal).filter(
                    Goal.id == goal.id
                ).delete(synchronize_session=False)

            db.query(LearnerSkill).filter(
                LearnerSkill.user_id == user.id
            ).delete(synchronize_session=False)

            db.commit()

        db.close()


def test_analysis_and_initial_skills_are_persisted(
    goal_context, monkeypatch
):
    db, goal, user = goal_context

    monkeypatch.setattr(
        "app.services.ai.goal_analyzer.get_llm_provider",
        lambda: FakeGoalProvider(json.dumps(valid_analysis())),
    )

    result = GoalAnalyzer(db).analyze(goal, user)

    saved = db.query(GoalAnalysis).filter(
        GoalAnalysis.goal_id == goal.id
    ).one()

    skills = (
        db.query(LearnerSkill)
        .filter(LearnerSkill.user_id == user.id)
        .order_by(LearnerSkill.skill)
        .all()
    )

    assert result.goal_id == goal.id
    assert saved.summary == "A practical learning plan."
    assert saved.skill_gaps == ["Kubernetes", "Linux"]
    assert saved.topics[0]["title"] == "Kubernetes basics"
    assert [skill.skill for skill in skills] == ["Kubernetes", "Linux"]
    assert all(skill.level == "beginner" for skill in skills)


def test_invalid_ai_response_writes_nothing(
    goal_context, monkeypatch
):
    db, goal, user = goal_context

    monkeypatch.setattr(
        "app.services.ai.goal_analyzer.get_llm_provider",
        lambda: FakeGoalProvider('{"summary": ""}'),
    )

    with pytest.raises(Exception):
        GoalAnalyzer(db).analyze(goal, user)

    assert db.query(GoalAnalysis).filter(
        GoalAnalysis.goal_id == goal.id
    ).count() == 0

    assert db.query(LearnerSkill).filter(
        LearnerSkill.user_id == user.id
    ).count() == 0


def test_skill_creation_failure_rolls_back_analysis(
    goal_context, monkeypatch
):
    db, goal, user = goal_context

    monkeypatch.setattr(
        "app.services.ai.goal_analyzer.get_llm_provider",
        lambda: FakeGoalProvider(json.dumps(valid_analysis())),
    )

    analyzer = GoalAnalyzer(db)

    def fail_skill_creation(**kwargs):
        raise RuntimeError("simulated skill creation failure")

    monkeypatch.setattr(
        analyzer.learner_skill_service,
        "create_initial_skills",
        fail_skill_creation,
    )

    with pytest.raises(
        RuntimeError, match="simulated skill creation failure"
    ):
        analyzer.analyze(goal, user)

    assert db.query(GoalAnalysis).filter(
        GoalAnalysis.goal_id == goal.id
    ).count() == 0

    assert db.query(LearnerSkill).filter(
        LearnerSkill.user_id == user.id
    ).count() == 0

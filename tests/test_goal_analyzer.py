import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
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

        yield db, goal, user, account

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
    db, goal, user, account = goal_context

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
    db, goal, user, account = goal_context

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
    db, goal, user, account = goal_context

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

def test_get_saved_goal_analysis(goal_context, monkeypatch):
    db, goal, user, account = goal_context
    account = None

    analysis = GoalAnalysis(
        goal_id=goal.id,
        summary="A practical learning plan.",
        learner_level="beginner",
        skill_gaps=["Kubernetes", "Linux"],
        topics=[
            {
                "title": "Kubernetes basics",
                "reason": "Understand core concepts",
                "priority": "high",
            }
        ],
        recommended_difficulty="beginner",
        learning_sequence=["Linux", "Kubernetes"],
        expectations="Deploy an application",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    account = user.id

    # Find the authenticated user's token through the test fixture.
    # The fixture is available to this test via verified_user_factory.
    # The account is created below using the fixture.



def test_get_saved_goal_analysis(goal_context):
    db, goal, user, account = goal_context

    analysis = GoalAnalysis(
        goal_id=goal.id,
        summary="A practical learning plan.",
        learner_level="beginner",
        skill_gaps=["Kubernetes", "Linux"],
        topics=[
            {
                "title": "Kubernetes basics",
                "reason": "Understand core concepts",
                "priority": "high",
            }
        ],
        recommended_difficulty="beginner",
        learning_sequence=["Linux", "Kubernetes"],
        expectations="Deploy an application",
    )
    db.add(analysis)
    db.commit()

    response = TestClient(app).get(
        f"/api/goals/{goal.id}/analysis",
        headers=account["headers"],
    )

    assert response.status_code == 200

    body = response.json()
    assert body["goal_id"] == goal.id
    assert body["summary"] == "A practical learning plan."
    assert body["skill_gaps"] == ["Kubernetes", "Linux"]
    assert body["topics"][0]["title"] == "Kubernetes basics"
    assert body["expectations"] == "Deploy an application"
    assert "id" in body
    assert "created_at" in body


def test_get_goal_analysis_not_found(goal_context):
    db, goal, user, account = goal_context

    response = TestClient(app).get(
        f"/api/goals/{goal.id}/analysis",
        headers=account["headers"],
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Goal analysis not found"

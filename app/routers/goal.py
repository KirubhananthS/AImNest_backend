from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.goal import Goal
from app.db.models.goal_task import GoalTask
from app.db.models.goal_milestone import GoalMilestone
from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user_from_access_token
from app.schemas.goal import GoalCreate, GoalRead, GoalUpdate
from app.schemas.goal_task import GoalTaskCreate, GoalTaskRead, GoalTaskUpdate
from app.schemas.goal_milestone import GoalMilestoneCreate, GoalMilestoneRead, GoalMilestoneUpdate

router = APIRouter(prefix="/api/goals", tags=["goals"])


def _get_current_user(db: Session, auth_payload: dict) -> User:
    user = db.query(User).filter(User.id == auth_payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _get_owned_goal(db: Session, goal_id: str, user: User) -> Goal:
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


def _clean_required(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail=f"Goal {field_name} must not be empty")
    return cleaned


def _get_owned_goal_task(db: Session, goal_id: str, task_id: str, user: User) -> GoalTask:
    task = (
        db.query(GoalTask)
        .join(Goal, Goal.id == GoalTask.goal_id)
        .filter(GoalTask.id == task_id, GoalTask.goal_id == goal_id, Goal.user_id == user.id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Goal task not found")
    return task


def _get_owned_goal_milestone(db: Session, goal_id: str, milestone_id: str, user: User) -> GoalMilestone:
    milestone = (
        db.query(GoalMilestone)
        .join(Goal, Goal.id == GoalMilestone.goal_id)
        .filter(
            GoalMilestone.id == milestone_id,
            GoalMilestone.goal_id == goal_id,
            Goal.user_id == user.id,
        )
        .first()
    )
    if not milestone:
        raise HTTPException(status_code=404, detail="Goal milestone not found")
    return milestone


@router.post("", response_model=GoalRead)
def create_goal(
    payload: GoalCreate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    goal = Goal(
        user_id=user.id,
        title=_clean_required(payload.title, "title"),
        description=_clean_required(payload.description, "description"),
        category=_clean_required(payload.category, "category"),
        priority=_clean_required(payload.priority, "priority"),
        deadline=payload.deadline,
        status=payload.status,
        progress=payload.progress,
        completed=payload.completed,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("", response_model=list[GoalRead])
def list_goals(
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    return db.query(Goal).filter(Goal.user_id == user.id).order_by(Goal.created_at.desc()).all()


@router.get("/{goal_id}", response_model=GoalRead)
def get_goal(
    goal_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    return _get_owned_goal(db, goal_id, user)


@router.patch("/{goal_id}", response_model=GoalRead)
def update_goal(
    goal_id: str,
    payload: GoalUpdate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    goal = _get_owned_goal(db, goal_id, user)
    updates = payload.model_dump(exclude_unset=True)

    for field_name in ("title", "description", "category", "priority"):
        if field_name in updates:
            updates[field_name] = _clean_required(updates[field_name], field_name)
    for field_name, value in updates.items():
        setattr(goal, field_name, value)
    goal.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{goal_id}")
def delete_goal(
    goal_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    goal = _get_owned_goal(db, goal_id, user)
    db.delete(goal)
    db.commit()
    return {"message": "Goal deleted"}


@router.post("/{goal_id}/tasks", response_model=GoalTaskRead)
def create_goal_task(
    goal_id: str,
    payload: GoalTaskCreate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    goal = _get_owned_goal(db, goal_id, user)
    title = _clean_required(payload.title, "task title")
    task = GoalTask(
        goal_id=goal.id,
        title=title,
        description=payload.description.strip() if payload.description else None,
        status=payload.status,
        due_date=payload.due_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{goal_id}/tasks", response_model=list[GoalTaskRead])
def list_goal_tasks(
    goal_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    goal = _get_owned_goal(db, goal_id, user)
    return db.query(GoalTask).filter(GoalTask.goal_id == goal.id).order_by(GoalTask.created_at.desc()).all()


@router.get("/{goal_id}/tasks/{task_id}", response_model=GoalTaskRead)
def get_goal_task(
    goal_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    _get_owned_goal(db, goal_id, user)
    return _get_owned_goal_task(db, goal_id, task_id, user)


@router.patch("/{goal_id}/tasks/{task_id}", response_model=GoalTaskRead)
def update_goal_task(
    goal_id: str,
    task_id: str,
    payload: GoalTaskUpdate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    task = _get_owned_goal_task(db, goal_id, task_id, user)
    updates = payload.model_dump(exclude_unset=True)
    if "title" in updates:
        updates["title"] = _clean_required(updates["title"], "task title")
    if "description" in updates:
        updates["description"] = updates["description"].strip() if updates["description"] else None
    for field_name, value in updates.items():
        setattr(task, field_name, value)
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{goal_id}/tasks/{task_id}")
def delete_goal_task(
    goal_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    task = _get_owned_goal_task(db, goal_id, task_id, user)
    db.delete(task)
    db.commit()
    return {"message": "Goal task deleted"}


@router.post("/{goal_id}/milestones", response_model=GoalMilestoneRead)
def create_goal_milestone(
    goal_id: str,
    payload: GoalMilestoneCreate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    goal = _get_owned_goal(db, goal_id, user)
    title = _clean_required(payload.title, "milestone title")
    milestone = GoalMilestone(goal_id=goal.id, title=title, status=payload.status)
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.get("/{goal_id}/milestones", response_model=list[GoalMilestoneRead])
def list_goal_milestones(
    goal_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    goal = _get_owned_goal(db, goal_id, user)
    return db.query(GoalMilestone).filter(GoalMilestone.goal_id == goal.id).order_by(GoalMilestone.created_at.desc()).all()


@router.get("/{goal_id}/milestones/{milestone_id}", response_model=GoalMilestoneRead)
def get_goal_milestone(
    goal_id: str,
    milestone_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    _get_owned_goal(db, goal_id, user)
    return _get_owned_goal_milestone(db, goal_id, milestone_id, user)


@router.patch("/{goal_id}/milestones/{milestone_id}", response_model=GoalMilestoneRead)
def update_goal_milestone(
    goal_id: str,
    milestone_id: str,
    payload: GoalMilestoneUpdate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    milestone = _get_owned_goal_milestone(db, goal_id, milestone_id, user)
    updates = payload.model_dump(exclude_unset=True)
    if "title" in updates:
        updates["title"] = _clean_required(updates["title"], "milestone title")
    for field_name, value in updates.items():
        setattr(milestone, field_name, value)
    milestone.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.delete("/{goal_id}/milestones/{milestone_id}")
def delete_goal_milestone(
    goal_id: str,
    milestone_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    milestone = _get_owned_goal_milestone(db, goal_id, milestone_id, user)
    db.delete(milestone)
    db.commit()
    return {"message": "Goal milestone deleted"}

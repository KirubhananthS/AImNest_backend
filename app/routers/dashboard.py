from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models.conversation import Conversation
from app.db.models.goal import Goal
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.models.workspace_activity import WorkspaceActivity
from app.db.models.workspace_member import WorkspaceMember
from app.db.models.workspace_task import WorkspaceTask
from app.db.session import get_db
from app.dependencies.auth import get_current_user_from_access_token
from app.schemas.dashboard import DashboardRead

router = APIRouter(prefix="/api", tags=["dashboard"])


def _get_current_user(db: Session, auth_payload: dict) -> User:
    user = db.query(User).filter(User.id == auth_payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _workspace_payload(workspace: Workspace) -> dict[str, Any]:
    return {
        "id": workspace.id,
        "name": workspace.name,
        "description": workspace.description,
        "ownerId": workspace.owner_id,
        "createdAt": workspace.created_at,
        "updatedAt": workspace.updated_at,
        "tasks": [
            {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority,
                "dueDate": task.due_date,
                "createdAt": task.created_at,
                "updatedAt": task.updated_at,
            }
            for task in sorted(workspace.tasks, key=lambda item: item.created_at, reverse=True)
        ],
    }


def _activity_payload(activity: WorkspaceActivity) -> dict[str, Any]:
    metadata = activity.event_metadata or {}
    return {
        "id": activity.id,
        "workspaceId": activity.workspace_id,
        "userId": activity.user_id,
        "action": activity.action,
        "description": activity.description,
        "createdAt": activity.created_at,
        "title": metadata.get("title"),
        "subtitle": metadata.get("subtitle"),
        "icon": metadata.get("icon"),
        "color": metadata.get("color"),
    }


def _goal_payload(goal: Goal) -> dict[str, Any]:
    return {
        "id": goal.id,
        "title": goal.title,
        "description": goal.description,
        "category": goal.category,
        "priority": goal.priority,
        "deadline": goal.deadline,
        "status": goal.status,
        "progress": goal.progress,
        "completed": goal.completed,
        "createdAt": goal.created_at,
        "updatedAt": goal.updated_at,
        "tasks": [
            {"id": task.id, "title": task.title, "description": task.description, "status": task.status, "dueDate": task.due_date}
            for task in sorted(goal.tasks, key=lambda item: item.created_at)
        ],
        "milestones": [
            {"id": milestone.id, "title": milestone.title, "status": milestone.status}
            for milestone in sorted(goal.milestones, key=lambda item: item.created_at)
        ],
    }


@router.get("/dashboard", response_model=DashboardRead)
def dashboard(
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    workspaces = (
        db.query(Workspace)
        .outerjoin(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .filter(or_(Workspace.owner_id == user.id, WorkspaceMember.user_id == user.id))
        .distinct()
        .order_by(Workspace.updated_at.desc())
        .all()
    )
    workspace_ids = [workspace.id for workspace in workspaces]
    activities = []
    if workspace_ids:
        activities = (
            db.query(WorkspaceActivity)
            .filter(WorkspaceActivity.workspace_id.in_(workspace_ids))
            .order_by(WorkspaceActivity.created_at.desc())
            .limit(20)
            .all()
        )
    goals = db.query(Goal).filter(Goal.user_id == user.id).order_by(Goal.updated_at.desc()).all()
    conversations = db.query(Conversation).filter(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc()).all()
    progress = round(sum(goal.progress for goal in goals) / len(goals)) if goals else 0

    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "bio": user.bio,
            "profileImage": user.profile_image,
            "level": user.level,
            "streak": user.streak,
            "createdAt": user.created_at,
            "updatedAt": user.updated_at,
        },
        "workspaces": [_workspace_payload(workspace) for workspace in workspaces],
        "currentCourse": None,
        "courses": [],
        "quickActions": [
            {"title": "Create Workspace", "icon": "add", "color": "purple"},
            {"title": "Add Goal", "icon": "flag", "color": "blue"},
            {"title": "Ask AI", "icon": "smart_toy", "color": "green"},
        ],
        "recentActivity": [_activity_payload(activity) for activity in activities],
        "aiSuggestions": [],
        "todayGoals": [_goal_payload(goal) for goal in goals],
        "conversations": [
            {"id": conversation.id, "title": conversation.title, "createdAt": conversation.created_at, "updatedAt": conversation.updated_at}
            for conversation in conversations
        ],
        "progress": progress,
    }

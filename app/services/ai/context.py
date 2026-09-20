"""User-scoped context retrieval for the AImNest assistant.

Every query in this module is scoped to the authenticated user:

* goals (and their tasks/milestones) belong strictly to the user, mirroring
  ``app/routers/goal.py``;
* workspaces are limited to those the user owns or is a member of, mirroring
  the access rule used by ``app/routers/dashboard.py`` and
  ``app/routers/workspace.py``.

No row may ever be loaded without ``user_id`` ownership or workspace
membership provenance: context is injected into an LLM prompt, so a leak
would be unrecoverable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models.goal import Goal
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.models.workspace_activity import WorkspaceActivity
from app.db.models.workspace_member import WorkspaceMember

DONE_STATUSES = {"done", "complete", "completed"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_overdue(value: Optional[datetime], now: datetime) -> bool:
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value < now


@dataclass(frozen=True)
class ContextTask:
    id: str
    title: str
    status: str
    due_date: Optional[datetime] = None
    is_overdue: bool = False
    is_open: bool = True


@dataclass(frozen=True)
class ContextMilestone:
    id: str
    title: str
    status: str


@dataclass(frozen=True)
class ContextGoal:
    id: str
    title: str
    description: str
    category: str
    priority: str
    deadline: Optional[date]
    status: str
    progress: int
    completed: bool
    is_overdue: bool
    tasks: tuple[ContextTask, ...] = ()
    milestones: tuple[ContextMilestone, ...] = ()

    @property
    def open_tasks(self) -> tuple[ContextTask, ...]:
        return tuple(task for task in self.tasks if task.is_open)


@dataclass(frozen=True)
class ContextActivity:
    action: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass(frozen=True)
class ContextWorkspace:
    id: str
    name: str
    description: Optional[str]
    role: str
    tasks: tuple[ContextTask, ...] = ()
    resources: tuple[str, ...] = ()
    activity: tuple[ContextActivity, ...] = ()

    @property
    def open_tasks(self) -> tuple[ContextTask, ...]:
        return tuple(task for task in self.tasks if task.is_open)


@dataclass(frozen=True)
class ContextProfile:
    id: str
    name: str
    level: str
    streak: int
    bio: Optional[str] = None
    language: str = "English"


@dataclass(frozen=True)
class AiContext:
    """Bounded, user-scoped snapshot of everything the assistant may see."""

    profile: Optional[ContextProfile] = None
    goals: tuple[ContextGoal, ...] = ()
    workspaces: tuple[ContextWorkspace, ...] = ()
    active_goal_count: int = 0
    completed_goal_count: int = 0
    overdue_goal_count: int = 0
    average_progress: int = 0
    sources: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.goals and not self.workspaces


class AssistantContextService:
    """Builds an :class:`AiContext` strictly from the user's own data."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Access scope
    # ------------------------------------------------------------------
    def accessible_workspace_ids(self, user: User) -> list[str]:
        """Workspace ids the user owns or is a member of."""
        rows = (
            self.db.query(Workspace.id)
            .outerjoin(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .filter(or_(Workspace.owner_id == user.id, WorkspaceMember.user_id == user.id))
            .distinct()
            .all()
        )
        return [row[0] for row in rows]

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def build(self, user: User) -> AiContext:
        now = _utc_now()
        today = now.date()

        goals = self._build_goals(user, today, now)
        workspaces = self._build_workspaces(user, now)
        sources = tuple(
            [f"goal:{goal.id}" for goal in goals]
            + [f"workspace:{workspace.id}" for workspace in workspaces]
        )

        return AiContext(
            profile=self._build_profile(user),
            goals=goals,
            workspaces=workspaces,
            sources=sources,
            **self._goal_stats(user, today),
        )

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------
    def _build_profile(self, user: User) -> ContextProfile:
        preferences = user.preferences
        return ContextProfile(
            id=user.id,
            name=user.name or "",
            level=user.level or "",
            streak=int(user.streak or 0),
            bio=user.bio,
            language=getattr(preferences, "language", None) or "English",
        )

    # ------------------------------------------------------------------
    # Goals
    # ------------------------------------------------------------------
    def _goal_stats(self, user: User, today: date) -> dict[str, int]:
        row = (
            self.db.query(
                func.count(Goal.id),
                func.sum(case((Goal.completed.is_(True), 1), else_=0)),
                func.sum(
                    case(
                        (and_(Goal.completed.is_(False), Goal.deadline < today), 1),
                        else_=0,
                    )
                ),
                func.avg(Goal.progress),
            )
            .filter(Goal.user_id == user.id)
            .one()
        )
        total = int(row[0] or 0)
        completed = int(row[1] or 0)
        return {
            "active_goal_count": max(total - completed, 0),
            "completed_goal_count": completed,
            "overdue_goal_count": int(row[2] or 0),
            "average_progress": int(round(float(row[3] or 0))),
        }

    def _build_goals(self, user: User, today: date, now: datetime) -> tuple[ContextGoal, ...]:
        limit = max(0, int(settings.ai_context_max_goals))
        if limit == 0:
            return ()
        rows = (
            self.db.query(Goal)
            .filter(Goal.user_id == user.id)
            .options(selectinload(Goal.tasks), selectinload(Goal.milestones))
            .order_by(Goal.completed.asc(), Goal.deadline.asc(), Goal.created_at.desc())
            .limit(limit)
            .all()
        )
        return tuple(self._goal_context(goal, today, now) for goal in rows)

    def _goal_context(self, goal: Goal, today: date, now: datetime) -> ContextGoal:
        tasks = tuple(
            self._task_context(task, now)
            for task in sorted(goal.tasks, key=lambda item: (not _is_open(item.status), item.created_at, item.id))
        )
        milestones = tuple(
            ContextMilestone(id=milestone.id, title=milestone.title, status=milestone.status)
            for milestone in sorted(goal.milestones, key=lambda item: (item.created_at, item.id))
        )
        return ContextGoal(
            id=goal.id,
            title=goal.title,
            description=goal.description,
            category=goal.category,
            priority=goal.priority,
            deadline=goal.deadline,
            status=goal.status,
            progress=int(goal.progress or 0),
            completed=bool(goal.completed),
            is_overdue=bool(
                not goal.completed and goal.deadline is not None and goal.deadline < today
            ),
            tasks=tasks,
            milestones=milestones,
        )

    # ------------------------------------------------------------------
    # Workspaces
    # ------------------------------------------------------------------
    def _build_workspaces(self, user: User, now: datetime) -> tuple[ContextWorkspace, ...]:
        limit = max(0, int(settings.ai_context_max_workspaces))
        if limit == 0:
            return ()
        rows = (
            self.db.query(Workspace)
            .outerjoin(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .filter(or_(Workspace.owner_id == user.id, WorkspaceMember.user_id == user.id))
            .options(selectinload(Workspace.tasks), selectinload(Workspace.resources))
            .distinct()
            .order_by(Workspace.updated_at.desc())
            .limit(limit)
            .all()
        )
        roles = {
            member.workspace_id: member.role
            for member in self.db.query(WorkspaceMember)
            .filter(WorkspaceMember.user_id == user.id)
            .all()
        }
        activities = self._activities_for([workspace.id for workspace in rows])
        return tuple(
            self._workspace_context(workspace, roles, activities, user, now) for workspace in rows
        )

    def _activities_for(self, workspace_ids: list[str]) -> dict[str, tuple[ContextActivity, ...]]:
        limit = max(0, int(settings.ai_context_max_activity))
        if not workspace_ids or limit == 0:
            return {}
        rows = (
            self.db.query(WorkspaceActivity)
            .filter(WorkspaceActivity.workspace_id.in_(workspace_ids))
            .order_by(WorkspaceActivity.created_at.desc())
            .all()
        )
        grouped: dict[str, list[ContextActivity]] = {}
        for activity in rows:
            bucket = grouped.setdefault(activity.workspace_id, [])
            if len(bucket) < limit:
                bucket.append(
                    ContextActivity(
                        action=activity.action,
                        description=activity.description,
                        created_at=activity.created_at,
                    )
                )
        return {workspace_id: tuple(items) for workspace_id, items in grouped.items()}

    def _workspace_context(
        self,
        workspace: Workspace,
        roles: dict[str, str],
        activities: dict[str, tuple[ContextActivity, ...]],
        user: User,
        now: datetime,
    ) -> ContextWorkspace:
        task_limit = max(0, int(settings.ai_context_max_workspace_tasks))
        ordered = sorted(
            workspace.tasks,
            key=lambda item: (not _is_open(item.status), item.created_at, item.id),
        )
        tasks = tuple(self._task_context(task, now) for task in ordered[:task_limit])
        return ContextWorkspace(
            id=workspace.id,
            name=workspace.name,
            description=workspace.description,
            role="owner" if workspace.owner_id == user.id else roles.get(workspace.id, "member"),
            tasks=tasks,
            resources=tuple(sorted(resource.name for resource in workspace.resources)),
            activity=activities.get(workspace.id, ()),
        )

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _task_context(self, task, now: datetime) -> ContextTask:
        is_open = _is_open(task.status)
        return ContextTask(
            id=task.id,
            title=task.title,
            status=task.status,
            due_date=task.due_date,
            is_overdue=is_open and _is_overdue(task.due_date, now),
            is_open=is_open,
        )


def _is_open(status: Optional[str]) -> bool:
    return (status or "").strip().lower() not in DONE_STATUSES
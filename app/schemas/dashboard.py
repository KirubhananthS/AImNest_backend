from typing import Any, Optional

from pydantic import BaseModel


class DashboardRead(BaseModel):
    user: dict[str, Any]
    workspaces: list[dict[str, Any]]
    currentCourse: Optional[dict[str, Any]] = None
    courses: list[dict[str, Any]]
    quickActions: list[dict[str, Any]]
    recentActivity: list[dict[str, Any]]
    aiSuggestions: list[dict[str, Any]]
    todayGoals: list[dict[str, Any]]
    conversations: list[dict[str, Any]]
    progress: int

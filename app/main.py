from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

from app.routers.auth import router as auth_router
from app.routers.workspace import router as workspace_router
from app.routers.goal import router as goal_router
from app.routers.conversation import router as conversation_router
from app.routers.dashboard import router as dashboard_router
from app.routers.notification import router as notification_router
from app.routers.settings import router as settings_router
from app.routers.ticket import router as ticket_router
app = FastAPI(
    title="AImNest Backend",
    version="1.0.0",
    description="AImNest backend API powered by mock in-memory data for auth, workspaces, goals, AI chat, dashboard, profile, settings, and resources.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ "http://localhost:3000",
    "http://127.0.0.1:3000",],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(goal_router)
app.include_router(conversation_router)
app.include_router(dashboard_router)
app.include_router(notification_router)
app.include_router(settings_router)
for route in ticket_router.routes:
    app.router.routes.append(route)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=4)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=6)
    phone: Optional[str] = None


class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp: str


class WorkspaceCreateRequest(BaseModel):
    name: str
    description: str
    goal: str
    category: str
    priority: str
    startDate: str
    endDate: str
    members: Optional[List[str]] = []


class GoalCreateRequest(BaseModel):
    title: str
    description: str
    category: str
    priority: str
    deadline: str
    completed: bool = False
    tasks: Optional[List[str]] = []
    milestones: Optional[List[str]] = []


class AIMessageRequest(BaseModel):
    message: str


users = [
    {
        "id": "usr_demo_001",
        "name": "Demo Learner",
        "email": "demo@aimnest.com",
        "password": "demo123",
        "phone": "+1 555 111 2233",
        "bio": "Learning cloud engineering and AI workflows.",
        "profileImage": "https://images.unsplash.com/photo-1500648767791-755569c0783d?auto=format&fit=crop&w=160&q=80",
        "level": "Rookie",
        "streak": 12,
        "preferences": {
            "language": "English",
            "themeMode": "light",
            "notificationsEnabled": True,
        },
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
]

workspaces = [
    {
        "id": "ws_aws_devops",
        "name": "AWS DevOps Practice",
        "description": "Build CI/CD pipelines and cloud deployment skills.",
        "goal": "Deploy a production-ready pipeline",
        "category": "DevOps",
        "priority": "High",
        "startDate": "2026-09-01",
        "endDate": "2026-10-30",
        "members": ["Demo Learner", "Sofia Khan", "Kai Moss"],
        "progress": 58,
        "createdAt": "2026-01-15T10:00:00Z",
        "updatedAt": "2026-01-18T10:00:00Z",
        "tasks": [
            {"id": "task_001", "title": "Create deployment checklist", "completed": True},
            {"id": "task_002", "title": "Configure GitHub Actions", "completed": False},
            {"id": "task_003", "title": "Set up environment secrets", "completed": False},
        ],
        "resources": [
            {"id": "res_001", "name": "aws-pipeline-guide.pdf", "size": "2 MB", "type": "PDF", "icon": "picture_as_pdf_rounded", "color": "red"},
            {"id": "res_002", "name": "docker-basics.yaml", "size": "1 MB", "type": "YAML", "icon": "code_rounded", "color": "green"},
        ],
        "activity": [
            {"title": "Workspace created", "subtitle": "AWS DevOps Practice", "icon": "dashboard_rounded", "color": "blue"},
            {"title": "Task updated", "subtitle": "Create deployment checklist", "icon": "check_circle_rounded", "color": "green"},
        ],
    },
    {
        "id": "ws_kubernetes",
        "name": "Kubernetes Learning",
        "description": "Understand pods, services, and cluster operations.",
        "goal": "Master Kubernetes fundamentals",
        "category": "Cloud",
        "priority": "Medium",
        "startDate": "2026-10-01",
        "endDate": "2026-12-01",
        "members": ["Demo Learner", "Luis Brown"],
        "progress": 36,
        "createdAt": "2026-02-05T10:00:00Z",
        "updatedAt": "2026-02-10T10:00:00Z",
        "tasks": [
            {"id": "task_101", "title": "Install kubectl locally", "completed": True},
            {"id": "task_102", "title": "Inspect pods and services", "completed": False},
        ],
        "resources": [
            {"id": "res_101", "name": "kubernetes-cheatsheet.pdf", "size": "4 MB", "type": "PDF", "icon": "picture_as_pdf_rounded", "color": "red"},
        ],
        "activity": [
            {"title": "Workspace created", "subtitle": "Kubernetes Learning", "icon": "dashboard_rounded", "color": "blue"},
        ],
    },
]

goals = [
    {
        "id": "goal_001",
        "title": "Launch Learning Roadmap",
        "description": "Create a roadmap for your cloud learning path.",
        "category": "Learning",
        "priority": "High",
        "deadline": "2026-10-15",
        "completed": False,
        "tasks": ["Create roadmap", "Audit skill gaps", "Choose learning path"],
        "milestones": ["Roadmap drafted", "Assessment completed"],
    },
    {
        "id": "goal_002",
        "title": "Review Cloud Operations",
        "description": "Study monitoring, incident response, and deployment workflows.",
        "category": "Operations",
        "priority": "Medium",
        "deadline": "2026-11-01",
        "completed": False,
        "tasks": ["Read incident playbook", "Create health checklist"],
        "milestones": ["Playbook reviewed"],
    },
]

conversations = [
    {
        "id": "conv_001",
        "title": "Cloud Learning",
        "createdAt": "2026-09-10T08:00:00Z",
        "updatedAt": "2026-09-10T08:15:00Z",
        "messages": [
            {"id": "msg_001", "sender": "user", "body": "Help me plan my cloud learning path.", "createdAt": "2026-09-10T08:00:00Z"},
            {"id": "msg_002", "sender": "assistant", "body": "Start with DevOps, cloud fundamentals, then deploy a learning project.", "createdAt": "2026-09-10T08:01:00Z"},
        ],
    },
]

activities = [
    {"title": "Workspace updated", "subtitle": "AWS DevOps Practice", "icon": "update_rounded", "color": "blue"},
    {"title": "Goal completed", "subtitle": "Launch Learning Roadmap", "icon": "check_circle_rounded", "color": "green"},
]

courses = [
    {"id": "course_001", "title": "AWS Foundations", "progress": 64, "lessons": 14, "remainingMinutes": 40},
    {"id": "course_002", "title": "DevOps Automation", "progress": 48, "lessons": 12, "remainingMinutes": 90},
]

suggestions = [
    {"title": "Create a learning sprint", "detail": "Finish your next lesson and update the workspace goal."},
    {"title": "Review your AWS deployment", "detail": "Compare your deployment checklist with your workspace resources."},
]

settings = {
    "themeMode": "light",
    "language": "English",
    "notificationsEnabled": True,
    "appVersion": "1.0.0",
}


@app.get("/")
def root():
    return {"message": "AImNest Backend is running"}


def register(request: RegisterRequest):
    existing = next((u for u in users if u["email"] == request.email), None)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    now = datetime.utcnow().isoformat() + "Z"
    user = {
        "id": f"usr_{uuid4().hex[:8]}",
        "name": request.name,
        "email": request.email,
        "password": request.password,
        "phone": request.phone,
        "bio": "",
        "profileImage": "",
        "level": "Rookie",
        "streak": 0,
        "preferences": {
            "language": "English",
            "themeMode": "light",
            "notificationsEnabled": True,
        },
        "createdAt": now,
        "updatedAt": now,
    }
    users.append(user)

    return {
        "accessToken": "demo_access_token_generated",
        "refreshToken": "demo_refresh_token_generated",
        "user": user,
    }


def login(request: LoginRequest):
    user = next(
        (u for u in users if u["email"] == request.email and u["password"] == request.password),
        None,
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    safe_user = {k: user[k] for k in user if k != "password"}
    return {
        "accessToken": "demo_access_token",
        "refreshToken": "demo_refresh_token",
        "user": safe_user,
    }


def logout():
    return {"message": "Logged out successfully"}


def verify_otp(request: OTPVerifyRequest):
    if request.otp == "123456":
        return {"verified": True, "message": "OTP verified successfully"}
    raise HTTPException(status_code=400, detail="Invalid OTP")


def resend_otp(request: OTPVerifyRequest):
    return {"message": "OTP sent successfully", "expiresIn": 180}


def get_me():
    user = users[0]
    safe_user = {k: user[k] for k in user if k != "password"}
    return safe_user


def get_user_profile():
    return get_me()


def update_user_profile(payload: Dict[str, Any]):
    user = users[0]
    for key, value in payload.items():
        if key == "password":
            continue
        user[key] = value
    user["updatedAt"] = datetime.utcnow().isoformat() + "Z"
    safe_user = {k: user[k] for k in user if k != "password"}
    return {"message": "Profile updated", "user": safe_user}


def update_preferences(payload: Dict[str, Any]):
    users[0]["preferences"].update(payload)
    return {"message": "Preferences updated", "preferences": users[0]["preferences"]}


def list_workspaces(
    search: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default="updatedAt"),
):
    result = list(workspaces)
    if search:
        result = [w for w in result if search.lower() in w["name"].lower() or search.lower() in w["description"].lower()]
    if category:
        result = [w for w in result if w["category"].lower() == category.lower()]
    if priority:
        result = [w for w in result if w["priority"].lower() == priority.lower()]

    if sort == "name":
        result.sort(key=lambda item: item["name"])
    elif sort == "priority":
        result.sort(key=lambda item: {"High": 1, "Medium": 2, "Low": 3}.get(item["priority"], 9))

    return result


def create_workspace(payload: WorkspaceCreateRequest):
    now = datetime.utcnow().isoformat() + "Z"
    workspace = {
        "id": f"ws_{uuid4().hex[:8]}",
        "name": payload.name,
        "description": payload.description,
        "goal": payload.goal,
        "category": payload.category,
        "priority": payload.priority,
        "startDate": payload.startDate,
        "endDate": payload.endDate,
        "members": payload.members or [users[0]["name"]],
        "progress": 0,
        "createdAt": now,
        "updatedAt": now,
        "tasks": [],
        "resources": [],
        "activity": [{"title": "Workspace created", "subtitle": payload.name, "icon": "dashboard_rounded", "color": "blue"}],
    }
    workspaces.append(workspace)
    return workspace


def get_workspace(workspace_id: str):
    workspace = next((w for w in workspaces if w["id"] == workspace_id), None)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def update_workspace(workspace_id: str, payload: Dict[str, Any]):
    workspace = next((w for w in workspaces if w["id"] == workspace_id), None)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace.update(payload)
    workspace["updatedAt"] = datetime.utcnow().isoformat() + "Z"
    return workspace


def delete_workspace(workspace_id: str):
    global workspaces
    old_count = len(workspaces)
    workspaces = [w for w in workspaces if w["id"] != workspace_id]
    if len(workspaces) == old_count:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"message": "Workspace deleted"}


def workspace_members(workspace_id: str):
    workspace = next((w for w in workspaces if w["id"] == workspace_id), None)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return [{"name": member, "role": "Owner" if idx == 0 else "Member"} for idx, member in enumerate(workspace.get("members", []))]


def add_workspace_member(workspace_id: str, payload: Dict[str, Any]):
    workspace = next((w for w in workspaces if w["id"] == workspace_id), None)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    member_name = payload.get("name", "")
    if not member_name:
        raise HTTPException(status_code=400, detail="Member name is required")
    workspace.setdefault("members", []).append(member_name)
    workspace.setdefault("activity", []).insert(0, {"title": "Member added", "subtitle": member_name, "icon": "person_add_alt_1_rounded", "color": "blue"})
    return {"message": "Member added", "members": workspace["members"]}


def workspace_tasks(workspace_id: str):
    workspace = next((w for w in workspaces if w["id"] == workspace_id), None)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace.get("tasks", [])


def add_workspace_task(workspace_id: str, payload: Dict[str, Any]):
    workspace = next((w for w in workspaces if w["id"] == workspace_id), None)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    title = payload.get("title", "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Task title is required")
    task = {"id": f"task_{uuid4().hex[:8]}", "title": title, "completed": False}
    workspace.setdefault("tasks", []).append(task)
    workspace.setdefault("activity", []).insert(0, {"title": "Task added", "subtitle": title, "icon": "add_task_rounded", "color": "purple"})
    return task


def update_workspace_task(workspace_id: str, task_id: str, payload: Dict[str, Any]):
    workspace = next((w for w in workspaces if w["id"] == workspace_id), None)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    for task in workspace.get("tasks", []):
        if task["id"] == task_id:
            task.update(payload)
            return task
    raise HTTPException(status_code=404, detail="Task not found")


def workspace_resources(workspace_id: str):
    workspace = next((w for w in workspaces if w["id"] == workspace_id), None)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace.get("resources", [])


def add_workspace_resource(workspace_id: str, payload: Dict[str, Any]):
    workspace = next((w for w in workspaces if w["id"] == workspace_id), None)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

    name = payload.get("name", "resource")
    size = payload.get("size", "Unknown size")
    extension = name.split(".")[-1].upper() if "." in name else "FILE"
    icon = "insert_drive_file_rounded"
    color = "accent"
    if extension == "PDF":
        icon = "picture_as_pdf_rounded"
        color = "red"
    elif extension in {"DOCX", "DOC"}:
        icon = "description_rounded"
        color = "blue"
    elif extension in {"YML", "YAML", "JSON"}:
        icon = "code_rounded"
        color = "green"

    resource = {
        "id": f"res_{uuid4().hex[:8]}",
        "name": name,
        "size": size,
        "type": extension,
        "icon": icon,
        "color": color,
    }
    workspace.setdefault("resources", []).append(resource)
    workspace.setdefault("activity", []).insert(0, {"title": "Resource added", "subtitle": name, "icon": "upload_file_rounded", "color": "green"})
    return resource


def workspace_activity(workspace_id: str):
    workspace = next((w for w in workspaces if w["id"] == workspace_id), None)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace.get("activity", [])


def list_goals():
    return goals


def create_goal(payload: GoalCreateRequest):
    goal = {
        "id": f"goal_{uuid4().hex[:8]}",
        "title": payload.title,
        "description": payload.description,
        "category": payload.category,
        "priority": payload.priority,
        "deadline": payload.deadline,
        "completed": payload.completed,
        "tasks": payload.tasks or [],
        "milestones": payload.milestones or [],
    }
    goals.append(goal)
    return goal


def get_goal(goal_id: str):
    goal = next((g for g in goals if g["id"] == goal_id), None)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


def update_goal(goal_id: str, payload: Dict[str, Any]):
    goal = next((g for g in goals if g["id"] == goal_id), None)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    goal.update(payload)
    return goal


def delete_goal(goal_id: str):
    global goals
    old_count = len(goals)
    goals = [g for g in goals if g["id"] != goal_id]
    if len(goals) == old_count:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"message": "Goal deleted"}


def list_conversations():
    return conversations


def create_conversation(payload: Dict[str, Any] = None):
    conversation = {
        "id": f"conv_{uuid4().hex[:8]}",
        "title": payload.get("title", "New Chat") if payload else "New Chat",
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "updatedAt": datetime.utcnow().isoformat() + "Z",
        "messages": [],
    }
    conversations.append(conversation)
    return conversation


def get_conversation(conversation_id: str):
    conversation = next((c for c in conversations if c["id"] == conversation_id), None)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def send_message(conversation_id: str, payload: AIMessageRequest):
    conversation = next((c for c in conversations if c["id"] == conversation_id), None)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user_message = {
        "id": f"msg_{uuid4().hex[:8]}",
        "sender": "user",
        "body": payload.message,
        "createdAt": datetime.utcnow().isoformat() + "Z",
    }
    ai_message = {
        "id": f"msg_{uuid4().hex[:8]}",
        "sender": "assistant",
        "body": f"AImNest AI: I can help you plan your next step for '{payload.message[:60]}'.",
        "createdAt": datetime.utcnow().isoformat() + "Z",
    }
    conversation.setdefault("messages", []).append(user_message)
    conversation.setdefault("messages", []).append(ai_message)
    conversation["updatedAt"] = datetime.utcnow().isoformat() + "Z"
    return {"message": ai_message, "conversation": conversation}


def delete_conversation(conversation_id: str):
    global conversations
    old_count = len(conversations)
    conversations = [c for c in conversations if c["id"] != conversation_id]
    if len(conversations) == old_count:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": "Conversation deleted"}


def dashboard():
    return {
        "user": users[0],
        "currentCourse": courses[0],
        "courses": courses,
        "quickActions": [
            {"title": "Create Workspace", "icon": "add", "color": "purple"},
            {"title": "Add Goal", "icon": "flag", "color": "blue"},
            {"title": "Ask AI", "icon": "smart_toy", "color": "green"},
        ],
        "recentActivity": activities,
        "aiSuggestions": suggestions,
        "todayGoals": goals,
        "progress": 72,
    }


def settings_endpoint():
    return settings


def update_settings_preferences(payload: Dict[str, Any]):
    settings.update(payload)
    return {"message": "Settings updated", "settings": settings}


def notifications():
    return [
        {"id": "notif_001", "title": "Workspace update", "body": "AWS DevOps Practice has a new activity.", "read": False},
        {"id": "notif_002", "title": "Goal deadline", "body": "Launch Learning Roadmap is due soon.", "read": False},
    ]


def mark_notification_read(notification_id: str):
    return {"message": "Notification marked as read", "id": notification_id}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "AImNest Backend", "timestamp": datetime.utcnow().isoformat() + "Z"}

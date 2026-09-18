from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user_from_access_token
from app.db.session import get_db
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.models.workspace_member import WorkspaceMember
from app.db.models.workspace_task import WorkspaceTask
from app.db.models.workspace_resource import WorkspaceResource
from app.db.models.workspace_activity import WorkspaceActivity
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate, WorkspaceRead
from app.schemas.workspace_member import WorkspaceMemberCreate, WorkspaceMemberRead, WorkspaceMemberRoleUpdate
from app.schemas.workspace_task import WorkspaceTaskCreate, WorkspaceTaskRead, WorkspaceTaskUpdate
from app.schemas.workspace_resource import WorkspaceResourceCreate, WorkspaceResourceRead
from app.schemas.workspace_activity import WorkspaceActivityRead

router = APIRouter(prefix="/api", tags=["workspace"])


def _get_current_user(db: Session, auth_payload: dict) -> User:
    user = db.query(User).filter(User.id == auth_payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@router.post("/workspaces", response_model=WorkspaceRead)
def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Workspace name must not be empty")

    description = payload.description.strip() if payload.description else None
    workspace = Workspace(owner_id=user.id, name=name, description=description)
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    _record_activity(db, workspace.id, user.id, "workspace_created", payload.name, {
        "title": "Workspace created",
        "subtitle": payload.name,
        "icon": "dashboard_rounded",
        "color": "blue",
    })
    db.commit()
    db.refresh(workspace)
    return workspace


@router.get("/workspaces", response_model=list[WorkspaceRead])
def list_workspaces(
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    return db.query(Workspace).filter(Workspace.owner_id == user.id).order_by(Workspace.created_at.desc()).all()


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceRead)
def get_workspace(
    workspace_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if workspace.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceRead)
def update_workspace(
    workspace_id: str,
    payload: WorkspaceUpdate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if workspace.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Workspace name must not be empty")
        workspace.name = name
    if payload.description is not None:
        workspace.description = payload.description.strip() if payload.description.strip() else None

    workspace.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(workspace)
    return workspace


@router.delete("/workspaces/{workspace_id}")
def delete_workspace(
    workspace_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if workspace.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    db.delete(workspace)
    db.commit()
    return {"message": "Workspace deleted"}


def _get_workspace_for_user(db: Session, workspace_id: str, user: User) -> Workspace:
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    is_owner = workspace.owner_id == user.id
    is_member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user.id,
    ).first()
    if not is_owner and not is_member:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def _get_owned_workspace(db: Session, workspace_id: str, user: User) -> Workspace:
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if workspace.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return workspace


def _member_response(member: WorkspaceMember) -> dict:
    return {
        "id": member.id,
        "workspace_id": member.workspace_id,
        "user_id": member.user_id,
        "role": member.role,
        "created_at": member.created_at,
        "user_name": member.user.name if member.user else None,
        "user_email": member.user.email if member.user else None,
    }


def _record_activity(
    db: Session,
    workspace_id: str,
    user_id: str,
    action: str,
    description: str,
    event_metadata: dict,
) -> None:
    db.add(WorkspaceActivity(
        workspace_id=workspace_id,
        user_id=user_id,
        action=action,
        description=description,
        event_metadata=event_metadata,
    ))


def _activity_response(activity: WorkspaceActivity) -> dict:
    event_metadata = activity.event_metadata or {}
    return {
        "id": activity.id,
        "workspace_id": activity.workspace_id,
        "user_id": activity.user_id,
        "action": activity.action,
        "description": activity.description,
        "metadata": event_metadata,
        "created_at": activity.created_at,
        "title": event_metadata.get("title"),
        "subtitle": event_metadata.get("subtitle"),
        "icon": event_metadata.get("icon"),
        "color": event_metadata.get("color"),
    }


@router.post("/workspaces/{workspace_id}/members", response_model=WorkspaceMemberRead)
def add_workspace_member(
    workspace_id: str,
    payload: WorkspaceMemberCreate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    _get_owned_workspace(db, workspace_id, user)
    if payload.role.lower() == "owner":
        raise HTTPException(status_code=400, detail="The owner role cannot be assigned")

    member_user = None
    if payload.user_id:
        member_user = db.query(User).filter(User.id == payload.user_id).first()
    elif payload.email:
        member_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not member_user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == member_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="User is already a workspace member")

    member = WorkspaceMember(workspace_id=workspace_id, user_id=member_user.id, role=payload.role)
    db.add(member)
    _record_activity(db, workspace_id, user.id, "member_added", member_user.name, {
        "title": "Member added",
        "subtitle": member_user.name,
        "icon": "person_add_alt_1_rounded",
        "color": "blue",
    })
    db.commit()
    db.refresh(member)
    return _member_response(member)


@router.get("/workspaces/{workspace_id}/members", response_model=list[WorkspaceMemberRead])
def list_workspace_members(
    workspace_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    _get_workspace_for_user(db, workspace_id, user)
    members = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
    ).order_by(WorkspaceMember.created_at.asc()).all()
    return [_member_response(member) for member in members]


@router.patch("/workspaces/{workspace_id}/members/{member_id}", response_model=WorkspaceMemberRead)
def update_workspace_member_role(
    workspace_id: str,
    member_id: str,
    payload: WorkspaceMemberRoleUpdate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    _get_owned_workspace(db, workspace_id, user)
    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.id == member_id,
        WorkspaceMember.workspace_id == workspace_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Workspace member not found")
    if member.user_id == user.id or member.role.lower() == "owner":
        raise HTTPException(status_code=400, detail="The owner membership cannot be demoted")
    if payload.role.lower() == "owner":
        raise HTTPException(status_code=400, detail="The owner role cannot be assigned")
    member.role = payload.role
    db.commit()
    db.refresh(member)
    return _member_response(member)


@router.delete("/workspaces/{workspace_id}/members/{member_id}")
def remove_workspace_member(
    workspace_id: str,
    member_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    _get_owned_workspace(db, workspace_id, user)
    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.id == member_id,
        WorkspaceMember.workspace_id == workspace_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Workspace member not found")
    if member.user_id == user.id or member.role.lower() == "owner":
        raise HTTPException(status_code=400, detail="The owner membership cannot be removed")
    db.delete(member)
    db.commit()
    return {"message": "Workspace member removed"}


@router.post("/workspaces/{workspace_id}/tasks", response_model=WorkspaceTaskRead)
def create_workspace_task(
    workspace_id: str,
    payload: WorkspaceTaskCreate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    _get_workspace_for_user(db, workspace_id, user)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Task title must not be empty")

    task = WorkspaceTask(
        workspace_id=workspace_id,
        title=title,
        description=payload.description.strip() if payload.description else None,
        status=payload.status,
        priority=payload.priority,
        due_date=payload.due_date,
    )
    db.add(task)
    _record_activity(db, workspace_id, user.id, "task_created", title, {
        "title": "Task added",
        "subtitle": title,
        "icon": "add_task_rounded",
        "color": "purple",
    })
    db.commit()
    db.refresh(task)
    return task


@router.get("/workspaces/{workspace_id}/tasks", response_model=list[WorkspaceTaskRead])
def list_workspace_tasks(
    workspace_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    _get_workspace_for_user(db, workspace_id, user)
    return db.query(WorkspaceTask).filter(
        WorkspaceTask.workspace_id == workspace_id,
    ).order_by(WorkspaceTask.created_at.desc()).all()


@router.get("/workspaces/{workspace_id}/tasks/{task_id}", response_model=WorkspaceTaskRead)
def get_workspace_task(
    workspace_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    _get_workspace_for_user(db, workspace_id, user)
    task = db.query(WorkspaceTask).filter(
        WorkspaceTask.id == task_id,
        WorkspaceTask.workspace_id == workspace_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/workspaces/{workspace_id}/tasks/{task_id}", response_model=WorkspaceTaskRead)
def update_workspace_task(
    workspace_id: str,
    task_id: str,
    payload: WorkspaceTaskUpdate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    _get_workspace_for_user(db, workspace_id, user)
    task = db.query(WorkspaceTask).filter(
        WorkspaceTask.id == task_id,
        WorkspaceTask.workspace_id == workspace_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    updates = payload.model_dump(exclude_unset=True)
    if "title" in updates:
        title = updates["title"].strip()
        if not title:
            raise HTTPException(status_code=422, detail="Task title must not be empty")
        task.title = title
    if "description" in updates:
        task.description = updates["description"].strip() if updates["description"] else None
    if "status" in updates:
        task.status = updates["status"]
    if "priority" in updates:
        task.priority = updates["priority"]
    if "due_date" in updates:
        task.due_date = updates["due_date"]
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/workspaces/{workspace_id}/tasks/{task_id}")
def delete_workspace_task(
    workspace_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    _get_workspace_for_user(db, workspace_id, user)
    task = db.query(WorkspaceTask).filter(
        WorkspaceTask.id == task_id,
        WorkspaceTask.workspace_id == workspace_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"message": "Task deleted"}


@router.post("/workspaces/{workspace_id}/resources", response_model=WorkspaceResourceRead)
def create_workspace_resource(
    workspace_id: str,
    payload: WorkspaceResourceCreate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    _get_workspace_for_user(db, workspace_id, user)
    name = payload.name.strip()
    resource_type = payload.type.strip()
    if not name or not resource_type:
        raise HTTPException(status_code=422, detail="Resource name and type must not be empty")

    resource = WorkspaceResource(
        workspace_id=workspace_id,
        name=name,
        size=payload.size.strip() if payload.size else None,
        type=resource_type,
        icon=payload.icon.strip() if payload.icon else None,
        color=payload.color.strip() if payload.color else None,
    )
    db.add(resource)
    _record_activity(db, workspace_id, user.id, "resource_created", name, {
        "title": "Resource added",
        "subtitle": name,
        "icon": "upload_file_rounded",
        "color": "green",
    })
    db.commit()
    db.refresh(resource)
    return resource


@router.get("/workspaces/{workspace_id}/resources", response_model=list[WorkspaceResourceRead])
def list_workspace_resources(
    workspace_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    _get_workspace_for_user(db, workspace_id, user)
    return db.query(WorkspaceResource).filter(
        WorkspaceResource.workspace_id == workspace_id,
    ).order_by(WorkspaceResource.created_at.desc()).all()


@router.get("/workspaces/{workspace_id}/resources/{resource_id}", response_model=WorkspaceResourceRead)
def get_workspace_resource(
    workspace_id: str,
    resource_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    _get_workspace_for_user(db, workspace_id, user)
    resource = db.query(WorkspaceResource).filter(
        WorkspaceResource.id == resource_id,
        WorkspaceResource.workspace_id == workspace_id,
    ).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource


@router.get("/workspaces/{workspace_id}/activity", response_model=list[WorkspaceActivityRead])
def list_workspace_activity(
    workspace_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    _get_workspace_for_user(db, workspace_id, user)
    activities = db.query(WorkspaceActivity).filter(
        WorkspaceActivity.workspace_id == workspace_id,
    ).order_by(WorkspaceActivity.created_at.desc()).all()
    return [_activity_response(activity) for activity in activities]

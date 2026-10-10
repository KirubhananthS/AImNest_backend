import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.models.otp_request import OTPRequest
from app.db.models.user import User
from app.db.models.workspace_member import WorkspaceMember
from app.db.models.workspace_activity import WorkspaceActivity
from app.db.models.goal import Goal
from app.db.models.goal_task import GoalTask
from app.db.models.goal_milestone import GoalMilestone
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.db.models.notification import Notification
from app.db.models.user_preferences import UserPreferences
from app.db.models.refresh_token import RefreshToken
from app.db.session import SessionLocal
from app.services.auth_service import AuthService
from app.core.config import settings
from app.core.security import verify_password

client = TestClient(app)

def verify_registered_user(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        assert user is not None

        service = AuthService(db)
        request, raw_otp = service.create_otp(
            user.id,
            channel="email",
            purpose="login",
        )

        assert request is not None
        assert len(raw_otp) == 6
        assert raw_otp.isdigit()
    finally:
        db.close()

    verify_resp = client.post(
        "/api/auth/verify-otp",
        json={
            "email": email,
            "otp": raw_otp,
        },
    )

    assert verify_resp.status_code == 200
    assert verify_resp.json()["verified"] is True


def test_workspace_core_crud_requires_auth_and_owner_scope():
    owner_email = f"workspace_owner_{uuid.uuid4().hex[:8]}@example.com"
    owner = client.post(
        "/api/auth/register",
        json={
            "name": "Workspace Owner",
            "email": owner_email,
            "password": "StrongPass123!",
            "phone": "+1234567890",
        },
    )
    assert owner.status_code == 200
    verify_registered_user(owner_email)
    owner_token = owner.json()["accessToken"]


    other_email = f"workspace_other_{uuid.uuid4().hex[:8]}@example.com"
    other = client.post(
        "/api/auth/register",
        json={
            "name": "Other User",
            "email": other_email,
            "password": "StrongPass123!",
            "phone": "+1234567890",
        },
    )
    assert other.status_code == 200
    verify_registered_user(other_email)
    other_token = other.json()["accessToken"]

    blank_headers = {}
    no_auth = client.get("/api/workspaces", headers=blank_headers)
    assert no_auth.status_code == 401

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    create = client.post(
        "/api/workspaces",
        headers=owner_headers,
        json={"name": "Workspace Core Test", "description": "temporary workspace"},
    )
    assert create.status_code == 200
    workspace = create.json()
    workspace_id = workspace["id"]

    list_resp = client.get("/api/workspaces", headers=owner_headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert any(item["id"] == workspace_id for item in data)

    fetch = client.get(f"/api/workspaces/{workspace_id}", headers=owner_headers)
    assert fetch.status_code == 200

    patch = client.patch(
        f"/api/workspaces/{workspace_id}",
        headers=owner_headers,
        json={"name": "Workspace Core Renamed", "description": "renamed"},
    )
    assert patch.status_code == 200
    assert patch.json()["name"] == "Workspace Core Renamed"

    other_headers = {"Authorization": f"Bearer {other_token}"}
    other_get = client.get(f"/api/workspaces/{workspace_id}", headers=other_headers)
    assert other_get.status_code == 404

    delete_resp = client.delete(f"/api/workspaces/{workspace_id}", headers=owner_headers)
    assert delete_resp.status_code == 200


def test_root_health_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "AImNest Backend is running"


def test_auth_login_endpoint_returns_tokens():
    response = client.post(
        "/api/auth/login",
        json={"email": "demo@aimnest.com", "password": "demo123"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "accessToken" in payload
    assert "refreshToken" in payload
    assert payload["user"]["email"] == "demo@aimnest.com"

def test_auth_refresh_endpoint_rejects_revoked_refresh_token():
    response = client.post(
        "/api/auth/login",
        json={"email": "demo@aimnest.com", "password": "demo123"},
    )

    assert response.status_code == 200

    refresh_token = response.json()["refreshToken"]

    import hashlib
    from app.services.token_service import TokenService

    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

    db = SessionLocal()
    try:
        TokenService(db).revoke_refresh_token(token_hash)
    finally:
        db.close()

    refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert refresh_response.status_code == 401

def test_refresh_token_reuse_revokes_token_family():
    response = client.post(
        "/api/auth/login",
        json={
            "email": "demo@aimnest.com",
            "password": "demo123",
        },
    )

    assert response.status_code == 200

    old_refresh_token = response.json()["refreshToken"]

    # First use: rotation must succeed.
    refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert refresh_response.status_code == 200

    new_refresh_token = refresh_response.json()["refreshToken"]
    assert new_refresh_token != old_refresh_token

def test_refresh_token_reuse_revokes_token_family():
    response = client.post(
        "/api/auth/login",
        json={"email": "demo@aimnest.com", "password": "demo123"},
    )

    assert response.status_code == 200

    old_refresh_token = response.json()["refreshToken"]

    refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert refresh_response.status_code == 200

    new_refresh_token = refresh_response.json()["refreshToken"]

    assert new_refresh_token != old_refresh_token

    reuse_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert reuse_response.status_code == 401

    family_reuse_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": new_refresh_token},
    )

    assert family_reuse_response.status_code == 401

    # Reusing the already-rotated token must be rejected.
    reuse_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert reuse_response.status_code == 401

    # H1 requirement:
    # Once refresh-token reuse is detected, the active token in the
    # same token family must also be invalidated.
    family_reuse_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": new_refresh_token},
    )

    assert family_reuse_response.status_code == 401

def test_auth_refresh_endpoint_validates_stored_refresh_token():
    response = client.post(
        "/api/auth/login",
        json={"email": "demo@aimnest.com", "password": "demo123"},
    )

    assert response.status_code == 200

    refresh_token = response.json()["refreshToken"]

    refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert refresh_response.status_code == 200

    payload = refresh_response.json()

    assert "accessToken" in payload
    assert "refreshToken" in payload
    assert payload["refreshToken"] != refresh_token

def test_refresh_token_reuse_revokes_token_family():
    response = client.post(
        "/api/auth/login",
        json={
            "email": "demo@aimnest.com",
            "password": "demo123",
        },
    )

    assert response.status_code == 200

    old_refresh_token = response.json()["refreshToken"]

    refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert refresh_response.status_code == 200

    new_refresh_token = refresh_response.json()["refreshToken"]
    assert new_refresh_token != old_refresh_token

    reuse_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert reuse_response.status_code == 401

    family_reuse_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": new_refresh_token},
    )

    assert family_reuse_response.status_code == 401


def test_auth_refresh_endpoint_rotates_refresh_token():
    response = client.post(
        "/api/auth/login",
        json={"email": "demo@aimnest.com", "password": "demo123"},
    )

    assert response.status_code == 200

    old_refresh_token = response.json()["refreshToken"]

    refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert refresh_response.status_code == 200

    payload = refresh_response.json()

    new_refresh_token = payload["refreshToken"]

    assert "accessToken" in payload
    assert "refreshToken" in payload
    assert new_refresh_token != old_refresh_token

def test_auth_logout_revokes_refresh_token():
    response = client.post(
        "/api/auth/login",
        json={"email": "demo@aimnest.com", "password": "demo123"},
    )

    assert response.status_code == 200

    refresh_token = response.json()["refreshToken"]

    logout_response = client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_token},
    )

    assert logout_response.status_code == 200
    assert logout_response.json()["message"] == "Logged out successfully"

    refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert refresh_response.status_code == 401

def test_register_issued_refresh_token_is_persisted_and_rotates():
    email = f"register_refresh_{uuid.uuid4().hex[:8]}@example.com"

    register = client.post(
        "/api/auth/register",
        json={
            "name": "Register Refresh User",
            "email": email,
            "password": "StrongPass123!",
            "phone": "+1234567890",
        },
    )
    assert register.status_code == 200
    original_refresh_token = register.json()["refreshToken"]

    # The registration response must hand back a token that was actually
    # persisted, otherwise the very next refresh call cannot succeed.
    import hashlib

    token_hash = hashlib.sha256(original_refresh_token.encode()).hexdigest()

    db = SessionLocal()
    try:
        stored = (
            db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )
        assert stored is not None
        assert stored.revoked is False
    finally:
        db.close()

    refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": original_refresh_token},
    )
    assert refresh_response.status_code == 200

    payload = refresh_response.json()
    assert "accessToken" in payload
    assert "refreshToken" in payload
    assert payload["refreshToken"] != original_refresh_token

    # The original token must have been consumed by the rotation.
    reused = client.post(
        "/api/auth/refresh",
        json={"refresh_token": original_refresh_token},
    )
    assert reused.status_code == 401


def test_register_creates_otp_request_row_and_hash():
    email = f"phase1_reg_otp_{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Phase1 OTP User",
            "email": email,
            "password": "StrongPass123!",
            "phone": "+1234567890",
        },
    )
    assert response.status_code == 200

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        assert user is not None

        otp_row = (
            db.query(OTPRequest)
            .filter(OTPRequest.user_id == user.id)
            .order_by(OTPRequest.created_at.desc())
            .first()
        )
        assert otp_row is not None
        assert otp_row.otp_hash.startswith("$argon2")
        assert otp_row.otp_hash != ""
        # hash-only storage contract: the real plaintext OTP should never be
        # persisted in the OTPRequest row.
        assert otp_row.otp_hash != "StrongPass123!"
    finally:
        db.close()


def test_verify_otp_flow_can_verify_and_reject_invalid_otp():
    email = f"phase1_verify_otp_{uuid.uuid4().hex[:8]}@example.com"
    register_resp = client.post(
        "/api/auth/register",
        json={
            "name": "Phase1 OTP Verify User",
            "email": email,
            "password": "StrongPass123!",
            "phone": "+1234567890",
        },
    )
    assert register_resp.status_code == 200

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        assert user is not None

        service = AuthService(db)
        request, raw_otp = service.create_otp(user.id, channel="email", purpose="login")
        assert request is not None
        assert len(raw_otp) == 6
        assert raw_otp.isdigit()

        verify_resp = client.post(
            "/api/auth/verify-otp",
            json={"email": email, "otp": raw_otp},
        )
        assert verify_resp.status_code == 200
        assert verify_resp.json()["verified"] is True

        db.expire_all()
        verified_user = db.query(User).filter(User.email == email.lower()).first()
        assert verified_user is not None
        assert verified_user.is_verified is True

        bad_resp = client.post(
            "/api/auth/verify-otp",
            json={"email": email, "otp": "000000"},
        )
        assert bad_resp.status_code == 400
        assert "Invalid or expired OTP" in bad_resp.json()["detail"]
    finally:
        db.close()


def test_workspace_list_endpoint_returns_workspaces():
    email = f"workspace_auth_list_{uuid.uuid4().hex[:8]}@example.com"
    register = client.post(
        "/api/auth/register",
        json={
            "name": "Workspace Auth List User",
            "email": email,
            "password": "StrongPass123!",
            "phone": "+1234567890",
        },
    )
    assert register.status_code == 200
    verify_registered_user(email)
    token = register.json()["accessToken"]

    response = client.get("/api/workspaces", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_workspace_members_owner_management_and_member_visibility():
    owner_email = f"member_owner_{uuid.uuid4().hex[:8]}@example.com"
    member_email = f"member_user_{uuid.uuid4().hex[:8]}@example.com"
    owner_register = client.post(
        "/api/auth/register",
        json={"name": "Member Owner", "email": owner_email, "password": "StrongPass123!", "phone": "+1234567890"},
    )
    member_register = client.post(
        "/api/auth/register",
        json={"name": "Member User", "email": member_email, "password": "StrongPass123!", "phone": "+1234567890"},
    )
    assert owner_register.status_code == 200
    assert member_register.status_code == 200
    verify_registered_user(owner_email)
    verify_registered_user(member_email)
    owner_headers = {"Authorization": f"Bearer {owner_register.json()['accessToken']}"}
    member_headers = {"Authorization": f"Bearer {member_register.json()['accessToken']}"}

    workspace_response = client.post(
        "/api/workspaces",
        headers=owner_headers,
        json={"name": "Members Test Workspace", "description": "member contract"},
    )
    assert workspace_response.status_code == 200
    workspace_id = workspace_response.json()["id"]
    member_user_id = member_register.json()["user"]["id"]

    add_response = client.post(
        f"/api/workspaces/{workspace_id}/members",
        headers=owner_headers,
        json={"user_id": member_user_id, "role": "editor"},
    )
    assert add_response.status_code == 200
    member_id = add_response.json()["id"]
    assert add_response.json()["role"] == "editor"

    duplicate_response = client.post(
        f"/api/workspaces/{workspace_id}/members",
        headers=owner_headers,
        json={"email": member_email, "role": "member"},
    )
    assert duplicate_response.status_code == 409

    owner_list = client.get(f"/api/workspaces/{workspace_id}/members", headers=owner_headers)
    assert owner_list.status_code == 200
    assert {item["user_id"] for item in owner_list.json()} == {
        owner_register.json()["user"]["id"],
        member_user_id,
    }

    member_list = client.get(f"/api/workspaces/{workspace_id}/members", headers=member_headers)
    assert member_list.status_code == 200

    role_response = client.patch(
        f"/api/workspaces/{workspace_id}/members/{member_id}",
        headers=owner_headers,
        json={"role": "viewer"},
    )
    assert role_response.status_code == 200
    assert role_response.json()["role"] == "viewer"

    forbidden_manage = client.delete(
        f"/api/workspaces/{workspace_id}/members/{member_id}",
        headers=member_headers,
    )
    assert forbidden_manage.status_code == 403

    remove_response = client.delete(
        f"/api/workspaces/{workspace_id}/members/{member_id}",
        headers=owner_headers,
    )
    assert remove_response.status_code == 200

    db = SessionLocal()
    try:
        assert db.query(WorkspaceMember).filter(WorkspaceMember.id == member_id).first() is None
    finally:
        db.close()


def test_workspace_task_crud_authorization_and_validation():
    owner_email = f"task_owner_{uuid.uuid4().hex[:8]}@example.com"
    member_email = f"task_member_{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"task_other_{uuid.uuid4().hex[:8]}@example.com"

    registrations = [
        ("Task Owner", owner_email),
        ("Task Member", member_email),
        ("Task Other", other_email),
    ]
    tokens = {}

    for name, email in registrations:
        response = client.post(
            "/api/auth/register",
            json={
                "name": name,
                "email": email,
                "password": "StrongPass123!",
                "phone": "+1234567890",
            },
        )
        assert response.status_code == 200
        verify_registered_user(email)
        tokens[email] = response.json()["accessToken"]

    owner_headers = {"Authorization": f"Bearer {tokens[owner_email]}"}
    member_headers = {"Authorization": f"Bearer {tokens[member_email]}"}
    other_headers = {"Authorization": f"Bearer {tokens[other_email]}"}


    workspace_response = client.post(
        "/api/workspaces",
        headers=owner_headers,
        json={"name": "Task Workspace", "description": "task contract"},
    )
    other_workspace_response = client.post(
        "/api/workspaces",
        headers=other_headers,
        json={"name": "Other Task Workspace", "description": "isolated"},
    )
    assert workspace_response.status_code == 200
    assert other_workspace_response.status_code == 200
    workspace_id = workspace_response.json()["id"]
    other_workspace_id = other_workspace_response.json()["id"]

    member_id = client.get(f"/api/auth/me", headers=member_headers).json()["sub"]
    add_member = client.post(
        f"/api/workspaces/{workspace_id}/members",
        headers=owner_headers,
        json={"user_id": member_id, "role": "member"},
    )
    assert add_member.status_code == 200

    no_auth = client.get(f"/api/workspaces/{workspace_id}/tasks")
    assert no_auth.status_code == 401

    invalid = client.post(
        f"/api/workspaces/{workspace_id}/tasks",
        headers=owner_headers,
        json={"description": "missing title"},
    )
    assert invalid.status_code == 422

    create = client.post(
        f"/api/workspaces/{workspace_id}/tasks",
        headers=owner_headers,
        json={
            "title": "Build task API",
            "description": "Implement persistence",
            "status": "todo",
            "priority": "high",
            "due_date": "2026-10-01T12:00:00Z",
        },
    )
    assert create.status_code == 200
    task = create.json()
    task_id = task["id"]
    assert task["workspace_id"] == workspace_id
    assert task["status"] == "todo"

    listing = client.get(f"/api/workspaces/{workspace_id}/tasks", headers=member_headers)
    assert listing.status_code == 200
    assert any(item["id"] == task_id for item in listing.json())

    fetched = client.get(f"/api/workspaces/{workspace_id}/tasks/{task_id}", headers=owner_headers)
    assert fetched.status_code == 200

    cross_workspace = client.get(
        f"/api/workspaces/{other_workspace_id}/tasks/{task_id}",
        headers=other_headers,
    )
    assert cross_workspace.status_code == 404

    updated = client.patch(
        f"/api/workspaces/{workspace_id}/tasks/{task_id}",
        headers=member_headers,
        json={"title": "Build task API v2", "status": "done"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Build task API v2"
    assert updated.json()["status"] == "done"

    deleted = client.delete(
        f"/api/workspaces/{workspace_id}/tasks/{task_id}",
        headers=owner_headers,
    )
    assert deleted.status_code == 200
    assert client.get(f"/api/workspaces/{workspace_id}/tasks/{task_id}", headers=owner_headers).status_code == 404


def test_workspace_resource_metadata_create_list_get_and_authorization():
    owner_email = f"resource_owner_{uuid.uuid4().hex[:8]}@example.com"
    member_email = f"resource_member_{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"resource_other_{uuid.uuid4().hex[:8]}@example.com"
    tokens = {}
    user_ids = {}
    for name, email in [
        ("Resource Owner", owner_email),
        ("Resource Member", member_email),
        ("Resource Other", other_email),
    ]:
        response = client.post(
            "/api/auth/register",
            json={"name": name, "email": email, "password": "StrongPass123!", "phone": "+1234567890"},
        )
        assert response.status_code == 200
        verify_registered_user(email)
        tokens[email] = response.json()["accessToken"]
        user_ids[email] = response.json()["user"]["id"]

    owner_headers = {"Authorization": f"Bearer {tokens[owner_email]}"}
    member_headers = {"Authorization": f"Bearer {tokens[member_email]}"}
    other_headers = {"Authorization": f"Bearer {tokens[other_email]}"}
    workspace_response = client.post(
        "/api/workspaces",
        headers=owner_headers,
        json={"name": "Resource Workspace", "description": "resource contract"},
    )
    assert workspace_response.status_code == 200
    workspace_id = workspace_response.json()["id"]

    add_member = client.post(
        f"/api/workspaces/{workspace_id}/members",
        headers=owner_headers,
        json={"user_id": user_ids[member_email], "role": "member"},
    )
    assert add_member.status_code == 200

    assert client.get(f"/api/workspaces/{workspace_id}/resources").status_code == 401
    invalid = client.post(
        f"/api/workspaces/{workspace_id}/resources",
        headers=owner_headers,
        json={"size": "2 MB", "type": "PDF"},
    )
    assert invalid.status_code == 422

    create = client.post(
        f"/api/workspaces/{workspace_id}/resources",
        headers=owner_headers,
        json={
            "name": "aws-pipeline-guide.pdf",
            "size": "2 MB",
            "type": "PDF",
            "icon": "picture_as_pdf_rounded",
            "color": "red",
        },
    )
    assert create.status_code == 200
    resource = create.json()
    resource_id = resource["id"]
    assert resource["workspace_id"] == workspace_id
    assert resource["name"] == "aws-pipeline-guide.pdf"

    member_list = client.get(f"/api/workspaces/{workspace_id}/resources", headers=member_headers)
    assert member_list.status_code == 200
    assert any(item["id"] == resource_id for item in member_list.json())

    fetched = client.get(
        f"/api/workspaces/{workspace_id}/resources/{resource_id}",
        headers=member_headers,
    )
    assert fetched.status_code == 200

    cross_workspace = client.get(
        f"/api/workspaces/{workspace_id}/resources/{resource_id}",
        headers=other_headers,
    )
    assert cross_workspace.status_code == 404


def test_workspace_activity_retrieval_persistence_and_authorization():
    owner_email = f"activity_owner_{uuid.uuid4().hex[:8]}@example.com"
    member_email = f"activity_member_{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"activity_other_{uuid.uuid4().hex[:8]}@example.com"
    users = []
    for name, email in [
        ("Activity Owner", owner_email),
        ("Activity Member", member_email),
        ("Activity Other", other_email),
    ]:
        response = client.post(
            "/api/auth/register",
            json={"name": name, "email": email, "password": "StrongPass123!", "phone": "+1234567890"},
        )
        assert response.status_code == 200
        verify_registered_user(email)
        users.append(response.json())

    owner_headers = {"Authorization": f"Bearer {users[0]['accessToken']}"}
    member_headers = {"Authorization": f"Bearer {users[1]['accessToken']}"}
    other_headers = {"Authorization": f"Bearer {users[2]['accessToken']}"}
    workspace = client.post(
        "/api/workspaces",
        headers=owner_headers,
        json={"name": "Activity Workspace", "description": "activity contract"},
    )
    assert workspace.status_code == 200
    workspace_id = workspace.json()["id"]

    add_member = client.post(
        f"/api/workspaces/{workspace_id}/members",
        headers=owner_headers,
        json={"user_id": users[1]["user"]["id"], "role": "member"},
    )
    assert add_member.status_code == 200
    create_task = client.post(
        f"/api/workspaces/{workspace_id}/tasks",
        headers=member_headers,
        json={"title": "Activity task"},
    )
    assert create_task.status_code == 200
    create_resource = client.post(
        f"/api/workspaces/{workspace_id}/resources",
        headers=owner_headers,
        json={"name": "guide.pdf", "type": "PDF"},
    )
    assert create_resource.status_code == 200

    activity = client.get(f"/api/workspaces/{workspace_id}/activity", headers=member_headers)
    assert activity.status_code == 200
    actions = {item["action"] for item in activity.json()}
    assert {"workspace_created", "member_added", "task_created", "resource_created"}.issubset(actions)
    assert activity.json()[0]["title"] in {"Resource added", "Task added", "Member added", "Workspace created"}

    no_auth = client.get(f"/api/workspaces/{workspace_id}/activity")
    assert no_auth.status_code == 401
    cross_workspace = client.get(f"/api/workspaces/{workspace_id}/activity", headers=other_headers)
    assert cross_workspace.status_code == 404

    db = SessionLocal()
    try:
        persisted = db.query(WorkspaceActivity).filter(WorkspaceActivity.workspace_id == workspace_id).all()
        assert len(persisted) >= 4
    finally:
        db.close()


def test_goal_crud_requires_auth_and_is_user_scoped():
    owner_email = f"goal_owner_{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"goal_other_{uuid.uuid4().hex[:8]}@example.com"
    registrations = []
    for name, email in [("Goal Owner", owner_email), ("Goal Other", other_email)]:
        response = client.post(
            "/api/auth/register",
            json={"name": name, "email": email, "password": "StrongPass123!", "phone": "+1234567890"},
        )
        assert response.status_code == 200
        verify_registered_user(email)
        registrations.append(response.json())

    owner_token = registrations[0]["accessToken"]
    other_token = registrations[1]["accessToken"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}

    assert client.get("/api/goals").status_code == 401
    invalid = client.post(
        "/api/goals",
        headers=owner_headers,
        json={"description": "missing title", "category": "Learning", "priority": "High", "deadline": "2026-10-15"},
    )
    assert invalid.status_code == 422

    create = client.post(
        "/api/goals",
        headers=owner_headers,
        json={
            "title": "Launch Goals Core",
            "description": "Persist the goal lifecycle",
            "category": "Backend",
            "priority": "High",
            "deadline": "2026-10-15",
            "status": "active",
            "progress": 25,
        },
    )
    assert create.status_code == 200
    goal = create.json()
    goal_id = goal["id"]
    assert goal["user_id"] == registrations[0]["user"]["id"]
    assert goal["progress"] == 25

    listing = client.get("/api/goals", headers=owner_headers)
    assert listing.status_code == 200
    assert any(item["id"] == goal_id for item in listing.json())
    assert client.get("/api/goals", headers=other_headers).json() == []

    fetched = client.get(f"/api/goals/{goal_id}", headers=owner_headers)
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Launch Goals Core"

    cross_get = client.get(f"/api/goals/{goal_id}", headers=other_headers)
    assert cross_get.status_code == 404
    cross_patch = client.patch(f"/api/goals/{goal_id}", headers=other_headers, json={"title": "Not allowed"})
    assert cross_patch.status_code == 404

    update = client.patch(
        f"/api/goals/{goal_id}",
        headers=owner_headers,
        json={"title": "Launch Goals Core v2", "progress": 100, "completed": True, "status": "completed"},
    )
    assert update.status_code == 200
    assert update.json()["title"] == "Launch Goals Core v2"
    assert update.json()["completed"] is True

    delete = client.delete(f"/api/goals/{goal_id}", headers=owner_headers)
    assert delete.status_code == 200
    assert client.get(f"/api/goals/{goal_id}", headers=owner_headers).status_code == 404

    db = SessionLocal()
    try:
        assert db.query(Goal).filter(Goal.id == goal_id).first() is None
    finally:
        db.close()


def test_goal_task_crud_requires_auth_and_is_goal_user_scoped():
    owner_email = f"goal_task_owner_{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"goal_task_other_{uuid.uuid4().hex[:8]}@example.com"
    registrations = []
    for name, email in [("Goal Task Owner", owner_email), ("Goal Task Other", other_email)]:
        response = client.post(
            "/api/auth/register",
            json={"name": name, "email": email, "password": "StrongPass123!", "phone": "+1234567890"},
        )
        assert response.status_code == 200
        verify_registered_user(email)
        registrations.append(response.json())

    owner_headers = {"Authorization": f"Bearer {registrations[0]['accessToken']}"}
    other_headers = {"Authorization": f"Bearer {registrations[1]['accessToken']}"}
    goal_response = client.post(
        "/api/goals",
        headers=owner_headers,
        json={
            "title": "Goal Task Parent",
            "description": "Own task records",
            "category": "Backend",
            "priority": "High",
            "deadline": "2026-10-20",
        },
    )
    assert goal_response.status_code == 200
    goal_id = goal_response.json()["id"]

    assert client.get(f"/api/goals/{goal_id}/tasks").status_code == 401
    invalid = client.post(f"/api/goals/{goal_id}/tasks", headers=owner_headers, json={"status": "pending"})
    assert invalid.status_code == 422

    create = client.post(
        f"/api/goals/{goal_id}/tasks",
        headers=owner_headers,
        json={"title": "Implement GoalTask", "description": "Persist task data", "status": "pending", "due_date": "2026-10-01T12:00:00Z"},
    )
    assert create.status_code == 200
    task = create.json()
    task_id = task["id"]
    assert task["goal_id"] == goal_id

    listing = client.get(f"/api/goals/{goal_id}/tasks", headers=owner_headers)
    assert listing.status_code == 200
    assert any(item["id"] == task_id for item in listing.json())
    fetched = client.get(f"/api/goals/{goal_id}/tasks/{task_id}", headers=owner_headers)
    assert fetched.status_code == 200

    cross_list = client.get(f"/api/goals/{goal_id}/tasks", headers=other_headers)
    cross_get = client.get(f"/api/goals/{goal_id}/tasks/{task_id}", headers=other_headers)
    cross_patch = client.patch(f"/api/goals/{goal_id}/tasks/{task_id}", headers=other_headers, json={"title": "Denied"})
    assert cross_list.status_code == 404
    assert cross_get.status_code == 404
    assert cross_patch.status_code == 404

    update = client.patch(
        f"/api/goals/{goal_id}/tasks/{task_id}",
        headers=owner_headers,
        json={"title": "Implement GoalTask v2", "status": "done"},
    )
    assert update.status_code == 200
    assert update.json()["title"] == "Implement GoalTask v2"
    assert update.json()["status"] == "done"

    delete = client.delete(f"/api/goals/{goal_id}/tasks/{task_id}", headers=owner_headers)
    assert delete.status_code == 200
    assert client.get(f"/api/goals/{goal_id}/tasks/{task_id}", headers=owner_headers).status_code == 404

    db = SessionLocal()
    try:
        assert db.query(GoalTask).filter(GoalTask.id == task_id).first() is None
    finally:
        db.close()


def test_goal_milestone_crud_requires_auth_and_is_goal_user_scoped():
    owner_email = f"milestone_owner_{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"milestone_other_{uuid.uuid4().hex[:8]}@example.com"
    registrations = []
    for name, email in [("Milestone Owner", owner_email), ("Milestone Other", other_email)]:
        response = client.post(
            "/api/auth/register",
            json={"name": name, "email": email, "password": "StrongPass123!", "phone": "+1234567890"},
        )
        assert response.status_code == 200
        verify_registered_user(email)
        registrations.append(response.json())

    owner_headers = {"Authorization": f"Bearer {registrations[0]['accessToken']}"}
    other_headers = {"Authorization": f"Bearer {registrations[1]['accessToken']}"}
    goal_response = client.post(
        "/api/goals",
        headers=owner_headers,
        json={
            "title": "Milestone Parent Goal",
            "description": "Own milestone records",
            "category": "Backend",
            "priority": "High",
            "deadline": "2026-10-20",
        },
    )
    assert goal_response.status_code == 200
    goal_id = goal_response.json()["id"]

    assert client.get(f"/api/goals/{goal_id}/milestones").status_code == 401
    invalid = client.post(f"/api/goals/{goal_id}/milestones", headers=owner_headers, json={"status": "pending"})
    assert invalid.status_code == 422

    create = client.post(
        f"/api/goals/{goal_id}/milestones",
        headers=owner_headers,
        json={"title": "Ship milestone API", "status": "pending"},
    )
    assert create.status_code == 200
    milestone = create.json()
    milestone_id = milestone["id"]
    assert milestone["goal_id"] == goal_id

    listing = client.get(f"/api/goals/{goal_id}/milestones", headers=owner_headers)
    assert listing.status_code == 200
    assert any(item["id"] == milestone_id for item in listing.json())
    fetched = client.get(f"/api/goals/{goal_id}/milestones/{milestone_id}", headers=owner_headers)
    assert fetched.status_code == 200

    cross_list = client.get(f"/api/goals/{goal_id}/milestones", headers=other_headers)
    cross_get = client.get(f"/api/goals/{goal_id}/milestones/{milestone_id}", headers=other_headers)
    cross_patch = client.patch(f"/api/goals/{goal_id}/milestones/{milestone_id}", headers=other_headers, json={"title": "Denied"})
    assert cross_list.status_code == 404
    assert cross_get.status_code == 404
    assert cross_patch.status_code == 404

    update = client.patch(
        f"/api/goals/{goal_id}/milestones/{milestone_id}",
        headers=owner_headers,
        json={"title": "Ship milestone API v2", "status": "done"},
    )
    assert update.status_code == 200
    assert update.json()["title"] == "Ship milestone API v2"
    assert update.json()["status"] == "done"

    delete = client.delete(f"/api/goals/{goal_id}/milestones/{milestone_id}", headers=owner_headers)
    assert delete.status_code == 200
    assert client.get(f"/api/goals/{goal_id}/milestones/{milestone_id}", headers=owner_headers).status_code == 404

    db = SessionLocal()
    try:
        assert db.query(GoalMilestone).filter(GoalMilestone.id == milestone_id).first() is None
    finally:
        db.close()


def test_conversation_crud_requires_auth_and_is_user_scoped():
    owner_email = f"conversation_owner_{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"conversation_other_{uuid.uuid4().hex[:8]}@example.com"
    registrations = []
    for name, email in [("Conversation Owner", owner_email), ("Conversation Other", other_email)]:
        response = client.post(
            "/api/auth/register",
            json={"name": name, "email": email, "password": "StrongPass123!", "phone": "+1234567890"},
        )
        assert response.status_code == 200
        verify_registered_user(email)
        registrations.append(response.json())

    owner_headers = {"Authorization": f"Bearer {registrations[0]['accessToken']}"}
    other_headers = {"Authorization": f"Bearer {registrations[1]['accessToken']}"}
    assert client.get("/api/ai/conversations").status_code == 401

    create = client.post(
        "/api/ai/conversations",
        headers=owner_headers,
        json={"title": "Persistent AI Conversation"},
    )
    assert create.status_code == 200
    conversation = create.json()
    conversation_id = conversation["id"]
    assert conversation["title"] == "Persistent AI Conversation"
    assert conversation["user_id"] == registrations[0]["user"]["id"]
    assert "createdAt" in conversation
    assert "updatedAt" in conversation

    listing = client.get("/api/ai/conversations", headers=owner_headers)
    assert listing.status_code == 200
    assert any(item["id"] == conversation_id for item in listing.json())

    fetched = client.get(f"/api/ai/conversations/{conversation_id}", headers=owner_headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == conversation_id

    cross_list = client.get("/api/ai/conversations", headers=other_headers)
    cross_get = client.get(f"/api/ai/conversations/{conversation_id}", headers=other_headers)
    cross_delete = client.delete(f"/api/ai/conversations/{conversation_id}", headers=other_headers)
    assert cross_list.status_code == 200
    assert cross_list.json() == []
    assert cross_get.status_code == 404
    assert cross_delete.status_code == 404

    delete = client.delete(f"/api/ai/conversations/{conversation_id}", headers=owner_headers)
    assert delete.status_code == 200
    assert client.get(f"/api/ai/conversations/{conversation_id}", headers=owner_headers).status_code == 404

    db = SessionLocal()
    try:
        assert db.query(Conversation).filter(Conversation.id == conversation_id).first() is None
    finally:
        db.close()


def test_message_creation_listing_authentication_and_cross_user_access():
    owner_email = f"message_owner_{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"message_other_{uuid.uuid4().hex[:8]}@example.com"
    registrations = []
    for name, email in [("Message Owner", owner_email), ("Message Other", other_email)]:
        response = client.post(
            "/api/auth/register",
            json={"name": name, "email": email, "password": "StrongPass123!", "phone": "+1234567890"},
        )
        assert response.status_code == 200
        verify_registered_user(email)
        registrations.append(response.json())

    owner_headers = {"Authorization": f"Bearer {registrations[0]['accessToken']}"}
    other_headers = {"Authorization": f"Bearer {registrations[1]['accessToken']}"}
    conversation = client.post(
        "/api/ai/conversations",
        headers=owner_headers,
        json={"title": "Message Contract Conversation"},
    )
    assert conversation.status_code == 200
    conversation_id = conversation.json()["id"]

    no_auth = client.get(f"/api/ai/conversations/{conversation_id}/messages")
    assert no_auth.status_code == 401
    invalid = client.post(
        f"/api/ai/conversations/{conversation_id}/messages",
        headers=owner_headers,
        json={"role": "user"},
    )
    assert invalid.status_code == 422

    create = client.post(
        f"/api/ai/conversations/{conversation_id}/messages",
        headers=owner_headers,
        json={"role": "user", "content": "Persist this message"},
    )
    assert create.status_code == 200
    message = create.json()
    message_id = message["id"]
    assert message["conversation_id"] == conversation_id
    assert message["role"] == "user"
    assert message["content"] == "Persist this message"
    assert message["body"] == "Persist this message"
    assert message["sender"] == "user"

    listing = client.get(f"/api/ai/conversations/{conversation_id}/messages", headers=owner_headers)
    assert listing.status_code == 200
    assert any(item["id"] == message_id for item in listing.json())

    cross_list = client.get(f"/api/ai/conversations/{conversation_id}/messages", headers=other_headers)
    assert cross_list.status_code == 404

    db = SessionLocal()
    try:
        persisted = db.query(Message).filter(Message.id == message_id).first()
        assert persisted is not None
        assert persisted.content == "Persist this message"
    finally:
        db.close()


def test_assistant_reply_persists_user_and_assistant_messages():
    owner_email = f"assistant_owner_{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"assistant_other_{uuid.uuid4().hex[:8]}@example.com"
    registrations = []
    for name, email in [("Assistant Owner", owner_email), ("Assistant Other", other_email)]:
        response = client.post(
            "/api/auth/register",
            json={"name": name, "email": email, "password": "StrongPass123!", "phone": "+1234567890"},
        )
        assert response.status_code == 200
        verify_registered_user(email)
        registrations.append(response.json())

    owner_headers = {"Authorization": f"Bearer {registrations[0]['accessToken']}"}
    other_headers = {"Authorization": f"Bearer {registrations[1]['accessToken']}"}
    conversation = client.post(
        "/api/ai/conversations",
        headers=owner_headers,
        json={"title": "Assistant Reply Conversation"},
    )
    assert conversation.status_code == 200
    conversation_id = conversation.json()["id"]

    no_auth = client.post(
        f"/api/ai/conversations/{conversation_id}/messages",
        json={"message": "Unauthenticated"},
    )
    assert no_auth.status_code == 401

    cross_user = client.post(
        f"/api/ai/conversations/{conversation_id}/messages",
        headers=other_headers,
        json={"message": "Cross user"},
    )
    assert cross_user.status_code == 404

    reply = client.post(
        f"/api/ai/conversations/{conversation_id}/messages",
        headers=owner_headers,
        json={"message": "Help me plan my next step."},
    )
    assert reply.status_code == 200
    response = reply.json()
    assert response["message"]["role"] == "assistant"
    assert "Help me plan my next step." in response["message"]["content"]
    assert response["conversation"]["id"] == conversation_id
    assert response["role"] == "user"

    messages = client.get(f"/api/ai/conversations/{conversation_id}/messages", headers=owner_headers)
    assert messages.status_code == 200
    assert [item["role"] for item in messages.json()] == ["user", "assistant"]

    db = SessionLocal()
    try:
        persisted = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).all()
        assert [item.role for item in persisted] == ["user", "assistant"]
        assert persisted[0].content == "Help me plan my next step."
    finally:
        db.close()


def test_dashboard_is_authenticated_and_user_scoped():
    owner_email = f"dashboard_owner_{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"dashboard_other_{uuid.uuid4().hex[:8]}@example.com"
    registrations = []
    for name, email in [("Dashboard Owner", owner_email), ("Dashboard Other", other_email)]:
        response = client.post(
            "/api/auth/register",
            json={"name": name, "email": email, "password": "StrongPass123!", "phone": "+1234567890"},
        )
        assert response.status_code == 200
        verify_registered_user(email)
        registrations.append(response.json())

    owner_headers = {"Authorization": f"Bearer {registrations[0]['accessToken']}"}
    other_headers = {"Authorization": f"Bearer {registrations[1]['accessToken']}"}
    assert client.get("/api/dashboard").status_code == 401

    owner_workspace = client.post(
        "/api/workspaces",
        headers=owner_headers,
        json={"name": "Owner Dashboard Workspace", "description": "owner data"},
    )
    other_workspace = client.post(
        "/api/workspaces",
        headers=other_headers,
        json={"name": "Other Dashboard Workspace", "description": "other data"},
    )
    assert owner_workspace.status_code == 200
    assert other_workspace.status_code == 200
    owner_workspace_id = owner_workspace.json()["id"]
    other_workspace_id = other_workspace.json()["id"]

    task = client.post(
        f"/api/workspaces/{owner_workspace_id}/tasks",
        headers=owner_headers,
        json={"title": "Dashboard task", "status": "todo"},
    )
    goal = client.post(
        "/api/goals",
        headers=owner_headers,
        json={
            "title": "Dashboard goal",
            "description": "Dashboard data",
            "category": "Backend",
            "priority": "High",
            "deadline": "2026-10-20",
            "progress": 40,
        },
    )
    conversation = client.post(
        "/api/ai/conversations",
        headers=owner_headers,
        json={"title": "Dashboard conversation"},
    )
    other_goal = client.post(
        "/api/goals",
        headers=other_headers,
        json={
            "title": "Other private goal",
            "description": "Must not appear",
            "category": "Private",
            "priority": "Low",
            "deadline": "2026-11-20",
        },
    )
    assert task.status_code == 200
    assert goal.status_code == 200
    assert conversation.status_code == 200
    assert other_goal.status_code == 200

    dashboard_response = client.get("/api/dashboard", headers=owner_headers)
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert dashboard["user"]["id"] == registrations[0]["user"]["id"]
    assert {item["id"] for item in dashboard["workspaces"]} == {owner_workspace_id}
    assert {item["id"] for item in dashboard["todayGoals"]} == {goal.json()["id"]}
    assert {item["id"] for item in dashboard["conversations"]} == {conversation.json()["id"]}
    assert dashboard["workspaces"][0]["tasks"][0]["id"] == task.json()["id"]
    assert dashboard["progress"] == 40
    assert other_workspace_id not in {item["id"] for item in dashboard["workspaces"]}
    assert other_goal.json()["id"] not in {item["id"] for item in dashboard["todayGoals"]}


def test_dashboard_for_new_user_returns_empty_persistent_collections():
    email = f"dashboard_empty_{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Empty Dashboard User",
            "email": email,
            "password": "StrongPass123!",
            "phone": "+1234567890",
        },
    )
    assert response.status_code == 200
    verify_registered_user(email)
    dashboard_response = client.get(
        "/api/dashboard",
        headers={"Authorization": f"Bearer {response.json()['accessToken']}"},
    )
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert dashboard["workspaces"] == []
    assert dashboard["todayGoals"] == []
    assert dashboard["conversations"] == []
    assert dashboard["recentActivity"] == []
    assert dashboard["progress"] == 0


def test_notifications_list_read_authentication_and_user_scope():
    owner_email = f"notification_owner_{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"notification_other_{uuid.uuid4().hex[:8]}@example.com"
    registrations = []
    for name, email in [("Notification Owner", owner_email), ("Notification Other", other_email)]:
        response = client.post(
            "/api/auth/register",
            json={"name": name, "email": email, "password": "StrongPass123!", "phone": "+1234567890"},
        )
        assert response.status_code == 200
        verify_registered_user(email)
        registrations.append(response.json())

    owner_id = registrations[0]["user"]["id"]
    other_id = registrations[1]["user"]["id"]
    owner_headers = {"Authorization": f"Bearer {registrations[0]['accessToken']}"}
    other_headers = {"Authorization": f"Bearer {registrations[1]['accessToken']}"}
    db = SessionLocal()
    try:
        owner_notification = Notification(user_id=owner_id, title="Workspace update", body="A workspace changed")
        other_notification = Notification(user_id=other_id, title="Private update", body="Other user data")
        db.add_all([owner_notification, other_notification])
        db.commit()
        db.refresh(owner_notification)
        db.refresh(other_notification)
        owner_notification_id = owner_notification.id
        other_notification_id = other_notification.id
    finally:
        db.close()

    no_auth = client.get("/api/notifications")
    assert no_auth.status_code == 401

    listing = client.get("/api/notifications", headers=owner_headers)
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [owner_notification_id]
    assert listing.json()[0]["read"] is False

    cross_read = client.patch(f"/api/notifications/{other_notification_id}/read", headers=owner_headers)
    assert cross_read.status_code == 404
    cross_list = client.get("/api/notifications", headers=other_headers)
    assert cross_list.status_code == 200
    assert [item["id"] for item in cross_list.json()] == [other_notification_id]

    mark_read = client.patch(f"/api/notifications/{owner_notification_id}/read", headers=owner_headers)
    assert mark_read.status_code == 200
    assert mark_read.json()["read"] is True

    listing_after = client.get("/api/notifications", headers=owner_headers)
    assert listing_after.status_code == 200
    assert listing_after.json()[0]["read"] is True


def test_settings_get_update_persistence_authentication_and_user_scope():
    owner_email = f"settings_owner_{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"settings_other_{uuid.uuid4().hex[:8]}@example.com"
    registrations = []
    for name, email in [("Settings Owner", owner_email), ("Settings Other", other_email)]:
        response = client.post(
            "/api/auth/register",
            json={"name": name, "email": email, "password": "StrongPass123!", "phone": "+1234567890"},
        )
        assert response.status_code == 200
        verify_registered_user(email)
        registrations.append(response.json())

    owner_id = registrations[0]["user"]["id"]
    owner_headers = {"Authorization": f"Bearer {registrations[0]['accessToken']}"}
    other_headers = {"Authorization": f"Bearer {registrations[1]['accessToken']}"}

    no_auth = client.get("/api/settings")
    assert no_auth.status_code == 401

    initial = client.get("/api/settings", headers=owner_headers)
    assert initial.status_code == 200
    assert initial.json() == {
        "language": "English",
        "themeMode": "light",
        "notificationsEnabled": True,
    }

    invalid = client.patch(
        "/api/settings/preferences",
        headers=owner_headers,
        json={"themeMode": "sepia"},
    )
    assert invalid.status_code == 422

    update = client.patch(
        "/api/settings/preferences",
        headers=owner_headers,
        json={"themeMode": "dark", "notificationsEnabled": False},
    )
    assert update.status_code == 200
    assert update.json()["settings"] == {
        "language": "English",
        "themeMode": "dark",
        "notificationsEnabled": False,
    }

    other_settings = client.get("/api/settings", headers=other_headers)
    assert other_settings.status_code == 200
    assert other_settings.json()["themeMode"] == "light"
    assert other_settings.json()["notificationsEnabled"] is True

    db = SessionLocal()
    try:
        preferences = db.query(UserPreferences).filter(UserPreferences.user_id == owner_id).first()
        assert preferences is not None
        assert preferences.theme_mode == "dark"
        assert preferences.notifications_enabled is False
    finally:
        db.close()

def test_notifications_unread_count_authentication_and_user_scope():
    owner_email = f"notification_count_owner_{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"notification_count_other_{uuid.uuid4().hex[:8]}@example.com"
    registrations = []

    for name, email in [
        ("Notification Count Owner", owner_email),
        ("Notification Count Other", other_email),
    ]:
        response = client.post(
            "/api/auth/register",
            json={
                "name": name,
                "email": email,
                "password": "StrongPass123!",
                "phone": "+1234567890",
            },
        )
        assert response.status_code == 200
        verify_registered_user(email)
        registrations.append(response.json())

    owner_id = registrations[0]["user"]["id"]
    other_id = registrations[1]["user"]["id"]
    owner_headers = {
        "Authorization": f"Bearer {registrations[0]['accessToken']}"
    }
    other_headers = {
        "Authorization": f"Bearer {registrations[1]['accessToken']}"
    }

    db = SessionLocal()
    try:
        db.add_all([
            Notification(
                user_id=owner_id,
                title="Unread one",
                body="First unread notification",
                is_read=False,
            ),
            Notification(
                user_id=owner_id,
                title="Unread two",
                body="Second unread notification",
                is_read=False,
            ),
            Notification(
                user_id=owner_id,
                title="Already read",
                body="Previously read notification",
                is_read=True,
            ),
            Notification(
                user_id=other_id,
                title="Other user unread",
                body="Must not be counted for owner",
                is_read=False,
            ),
        ])
        db.commit()
    finally:
        db.close()

    no_auth = client.get("/api/notifications/unread-count")
    assert no_auth.status_code == 401

    owner_response = client.get(
        "/api/notifications/unread-count",
        headers=owner_headers,
    )
    assert owner_response.status_code == 200
    assert owner_response.json() == {"unreadCount": 2}

    other_response = client.get(
        "/api/notifications/unread-count",
        headers=other_headers,
    )
    assert other_response.status_code == 200
    assert other_response.json() == {"unreadCount": 1}

def test_ai_conversation_endpoint_returns_conversation_and_message():
    email = f"conversation_legacy_{uuid.uuid4().hex[:8]}@example.com"
    register = client.post(
        "/api/auth/register",
        json={
            "name": "Conversation Legacy Test User",
            "email": email,
            "password": "StrongPass123!",
            "phone": "+1234567890",
        },
    )
    assert register.status_code == 200
    verify_registered_user(email)
    response = client.get(
        "/api/ai/conversations",
        headers={"Authorization": f"Bearer {register.json()['accessToken']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def _register_unverified_active_user(prefix: str) -> tuple[str, dict]:
    """Register (but do not OTP-verify) an active user and return its headers."""
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    register = client.post(
        "/api/auth/register",
        json={
            "name": "Unverified Active User",
            "email": email,
            "password": "StrongPass123!",
            "phone": "+1234567890",
        },
    )
    assert register.status_code == 200

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        assert user is not None
        assert user.is_active is True
        assert user.is_verified is False
    finally:
        db.close()

    return email, {"Authorization": f"Bearer {register.json()['accessToken']}"}


def test_unverified_active_user_allowed_when_verification_not_required(monkeypatch):
    monkeypatch.setattr(settings, "require_verified_user", False)
    _, headers = _register_unverified_active_user("unverified_allowed")

    response = client.get("/api/workspaces", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


def test_unverified_active_user_blocked_when_verification_required(monkeypatch):
    monkeypatch.setattr(settings, "require_verified_user", True)
    _, headers = _register_unverified_active_user("unverified_blocked")

    response = client.get("/api/workspaces", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "User account is not verified"


@pytest.mark.parametrize("require_verified_user", [False, True])
def test_inactive_user_blocked_in_both_verification_flag_states(
    monkeypatch, require_verified_user
):
    monkeypatch.setattr(settings, "require_verified_user", require_verified_user)
    email, headers = _register_unverified_active_user("inactive_flag")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        assert user is not None
        user.is_active = False
        db.commit()
    finally:
        db.close()

    response = client.get("/api/workspaces", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "User account is inactive"


def test_inactive_user_cannot_use_access_token():
    email = f"inactive_user_{uuid.uuid4().hex[:8]}@example.com"

    register_resp = client.post(
        "/api/auth/register",
        json={
            "name": "Inactive User",
            "email": email,
            "password": "StrongPass123!",
            "phone": "+1234567890",
        },
    )
    assert register_resp.status_code == 200

    access_token = register_resp.json()["accessToken"]

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        assert user is not None

        user.is_verified = True
        user.is_active = False
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/api/workspaces",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User account is inactive"

def test_resend_otp():
    email = f"resend_{uuid.uuid4().hex[:8]}@example.com"

    response = client.post(
        "/api/auth/register",
        json={
            "name": "Resend Test User",
            "email": email,
            "password": "StrongPass123!",
            "phone": "+1234567890",
        },
    )

    assert response.status_code == 200

    response = client.post(
        "/api/auth/resend-otp",
        json={
            "email": email,
            "otp": "",
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "OTP resent successfully"


def test_forgot_password():
    email = f"forgot_{uuid.uuid4().hex[:8]}@example.com"

    response = client.post(
        "/api/auth/register",
        json={
            "name": "Forgot Password User",
            "email": email,
            "password": "OldPassword123!",
            "phone": "+1234567890",
        },
    )

    assert response.status_code == 200

    response = client.post(
        "/api/auth/forgot-password",
        json={
            "email": email,
        },
    )

    assert response.status_code == 200
    assert (
        response.json()["message"]
        == "Password reset OTP sent successfully"
    )


def test_reset_password():
    email = f"reset_{uuid.uuid4().hex[:8]}@example.com"

    response = client.post(
        "/api/auth/register",
        json={
            "name": "Reset Password User",
            "email": email,
            "password": "OldPassword123!",
            "phone": "+1234567890",
        },
    )

    assert response.status_code == 200

    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.email == email.lower())
            .first()
        )

        assert user is not None

        _, raw_otp = AuthService(db).create_otp(
            user.id,
            channel="email",
            purpose="password_reset",
        )
    finally:
        db.close()

    response = client.post(
        "/api/auth/reset-password",
        json={
            "email": email,
            "otp": raw_otp,
            "new_password": "NewPassword123!",
        },
    )

    assert response.status_code == 200
    assert (
        response.json()["message"]
        == "Password reset successfully"
    )


def test_new_password_works_after_reset():
    email = f"reset_login_{uuid.uuid4().hex[:8]}@example.com"

    response = client.post(
        "/api/auth/register",
        json={
            "name": "Reset Login User",
            "email": email,
            "password": "OldPassword123!",
            "phone": "+1234567890",
        },
    )

    assert response.status_code == 200

    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.email == email.lower())
            .first()
        )

        assert user is not None

        _, raw_otp = AuthService(db).create_otp(
            user.id,
            channel="email",
            purpose="password_reset",
        )
    finally:
        db.close()

    response = client.post(
        "/api/auth/reset-password",
        json={
            "email": email,
            "otp": raw_otp,
            "new_password": "NewPassword123!",
        },
    )

    assert response.status_code == 200

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "NewPassword123!",
        },
    )

    assert login_response.status_code == 200

    old_login_response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "OldPassword123!",
        },
    )

    assert old_login_response.status_code == 401

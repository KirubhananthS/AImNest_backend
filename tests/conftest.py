"""Shared pytest fixtures.

The AI tests must never depend on a live Ollama server, so the LLM provider
dependency is globally overridden with ``None`` (the supported "assistant
disabled" signal). Individual tests can override it again with a fake provider.
"""

import os
import uuid

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy.engine import URL

load_dotenv()

os.environ["DATABASE_URL"] = URL.create(
    "postgresql+psycopg",
    username=os.environ["TEST_DB_USER"],
    password=os.environ["TEST_DB_PASSWORD"],
    host=os.environ.get("TEST_DB_HOST", "localhost"),
    port=int(os.environ.get("TEST_DB_PORT", "5432")),
    database=os.environ.get("TEST_DB_NAME", "aimnest_test"),
).render_as_string(hide_password=False)

from app.db.models.user import User
from app.db.session import SessionLocal
from app.main import app
from app.services.ai.provider_factory import get_llm_provider
from app.services.auth_service import AuthService



import uuid

import pytest
from fastapi.testclient import TestClient

from app.db.models.user import User
from app.db.session import SessionLocal
from app.main import app
from app.services.ai.provider_factory import get_llm_provider
from app.services.auth_service import AuthService


@pytest.fixture(autouse=True)
def disable_live_llm_provider():
    """Keep the suite hermetic and deterministic: no outbound Ollama calls."""
    app.dependency_overrides[get_llm_provider] = lambda: None
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)




@pytest.fixture(autouse=True)
def disable_real_email_sending(monkeypatch):
    """Prevent tests from sending real emails."""

    async def fake_send_email(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.email_service.EmailService.send_otp_email",
        fake_send_email,
    )
    monkeypatch.setattr(
        "app.services.email_service.EmailService.send_welcome_email",
        fake_send_email,
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

@pytest.fixture(autouse=True)
def seed_demo_user(disable_real_email_sending):
    db = SessionLocal()
    try:
        existing = db.query(User).filter(
            User.email == "demo@aimnest.com"
        ).first()

        if existing is None:
            AuthService(db).register(
                name="Demo User",
                email="demo@aimnest.com",
                password="demo123",
                phone="+1234567890",
            )
    finally:
        db.close()


@pytest.fixture
def verified_user_factory(client: TestClient):
    """Register and OTP-verify a fresh user, returning its token and id."""

    def _create(
        *,
        name: str = "AI Test User",
        password: str = "StrongPass123!",
        phone: str = "+1234567890",
    ) -> dict:
        email = f"ai_test_{uuid.uuid4().hex[:8]}@example.com"
        response = client.post(
            "/api/auth/register",
            json={"name": name, "email": email, "password": password, "phone": phone},
        )
        assert response.status_code == 200

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == email.lower()).first()
            assert user is not None
            _, raw_otp = AuthService(db).create_otp(user.id, channel="email", purpose="login")
        finally:
            db.close()

        verified = client.post("/api/auth/verify-otp", json={"email": email, "otp": raw_otp})
        assert verified.status_code == 200

        payload = response.json()
        return {
            "email": email,
            "token": payload["accessToken"],
            "user": payload["user"],
            "headers": {"Authorization": f"Bearer {payload['accessToken']}"},
        }

    return _create
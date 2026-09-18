from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password, generate_otp
from app.core.jwt_service import JWTService
from app.db.models.user import User
from app.db.models.otp_request import OTPRequest
from app.db.models.refresh_token import RefreshToken
from app.db.models.user_preferences import UserPreferences
from app.services.token_service import TokenService


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register(self, name: str, email: str, password: str, phone: Optional[str] = None):
        existing = self.db.query(User).filter(User.email == email.lower()).first()
        if existing:
            raise ValueError("Email already registered")

        user = User(
            name=name,
            email=email.lower(),
            phone=phone,
            password_hash=hash_password(password),
            level="Rookie",
            streak=0,
            is_active=True,
            is_verified=False,
            role="user",
        )
        self.db.add(user)
        self.db.flush()

        preferences = UserPreferences(user_id=user.id, language="English", theme_mode="light", notifications_enabled=True)
        self.db.add(preferences)
        self.db.commit()
        self.db.refresh(user)

        # Keep the current registration response shape unchanged and use the
        # existing OTP persistence service hook that hashes the OTP for the
        # otp_requests table without exposing plaintext OTP in a response.
        self.create_otp(user.id, channel="email", purpose="login")
        return user

    def login(self, email: str, password: str):
        user = self.db.query(User).filter(User.email == email.lower()).first()
        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")

        access_token = JWTService.create_access_token(user.id)
        refresh_token = JWTService.create_refresh_token(user.id)

        TokenService(self.db).store_refresh_token(
    user_id=user.id,
    token=refresh_token,
)
        return {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "phone": user.phone,
                "bio": user.bio,
                "profileImage": user.profile_image,
                "level": user.level,
                "streak": user.streak,
                "preferences": {
                    "language": user.preferences.language if user.preferences else "English",
                    "themeMode": user.preferences.theme_mode if user.preferences else "light",
                    "notificationsEnabled": user.preferences.notifications_enabled if user.preferences else True,
                },
                "createdAt": user.created_at.isoformat(),
                "updatedAt": user.updated_at.isoformat(),
            },
        }

    def create_otp(self, user_id: str, channel: str = "email", purpose: str = "login"):
        otp = generate_otp(length=6)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=180)
        otp_hash = hash_password(otp)
        request = OTPRequest(
            user_id=user_id,
            otp_hash=otp_hash,
            channel=channel,
            purpose=purpose,
            attempts=0,
            expires_at=expires_at,
            is_active=True,
        )
        self.db.add(request)
        self.db.commit()
        return request, otp

    def verify_otp_once(self, user_id: str, otp: str, purpose: str = "login"):
        pending = (
            self.db.query(OTPRequest)
            .filter(OTPRequest.user_id == user_id)
            .filter(OTPRequest.purpose == purpose)
            .filter(OTPRequest.is_active == True)
            .filter(OTPRequest.used_at.is_(None))
            .filter(OTPRequest.expires_at >= datetime.now(timezone.utc))
            .order_by(OTPRequest.created_at.desc())
            .first()
        )
        if not pending:
            return False

        if pending.attempts >= 3:
            return False

        verified = verify_password(otp, pending.otp_hash)
        if not verified:
            pending.attempts += 1
            self.db.commit()
            return False

        pending.used_at = datetime.now(timezone.utc)
        pending.is_active = False
        self.db.commit()
        return True

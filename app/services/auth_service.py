import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.jwt_service import JWTService
from app.core.security import generate_otp, hash_password, verify_password
from app.db.models.otp_request import OTPRequest
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User
from app.db.models.user_preferences import UserPreferences
from app.services.email_service import EmailService
from app.services.token_service import TokenService


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService()

    def register(
        self,
        name: str,
        email: str,
        password: str,
        phone: Optional[str] = None,
    ):
        normalized_email = email.lower()

        existing = (
            self.db.query(User)
            .filter(User.email == normalized_email)
            .first()
        )

        if existing:
            raise ValueError("Email already registered")

        user = User(
            name=name,
            email=normalized_email,
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

        preferences = UserPreferences(
            user_id=user.id,
            language="English",
            theme_mode="light",
            notifications_enabled=True,
        )

        self.db.add(preferences)

        self.db.commit()
        self.db.refresh(user)

        # Generate and persist registration OTP.
        # The OTP itself is never stored as plaintext.
        self.create_otp(
            user.id,
            channel="email",
            purpose="login",
            email=user.email,
        )

        return user

    def login(self, email: str, password: str):
        user = (
            self.db.query(User)
            .filter(User.email == email.lower())
            .first()
        )

        if not user or not verify_password(
            password,
            user.password_hash,
        ):
            raise ValueError("Invalid email or password")

        access_token = JWTService.create_access_token(user.id)
        refresh_token = JWTService.create_refresh_token(user.id)

        TokenService(self.db).store_refresh_token(
            user_id=user.id,
            token=refresh_token,
            family_id=str(uuid4()),
        )

        self.db.commit()

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
                    "language": (
                        user.preferences.language
                        if user.preferences
                        else "English"
                    ),
                    "themeMode": (
                        user.preferences.theme_mode
                        if user.preferences
                        else "light"
                    ),
                    "notificationsEnabled": (
                        user.preferences.notifications_enabled
                        if user.preferences
                        else True
                    ),
                },
                "createdAt": user.created_at.isoformat(),
                "updatedAt": user.updated_at.isoformat(),
            },
        }

    def create_otp(
        self,
        user_id: str,
        channel: str = "email",
        purpose: str = "login",
        email: Optional[str] = None,
    ):
        # Invalidate previous active OTPs for the same
        # user and purpose before creating a new one.
        self.db.query(OTPRequest).filter(
            OTPRequest.user_id == user_id,
            OTPRequest.purpose == purpose,
            OTPRequest.is_active == True,
            OTPRequest.used_at.is_(None),
        ).update(
            {
                OTPRequest.is_active: False,
            },
            synchronize_session=False,
        )

        self.db.commit()

        otp = generate_otp(
            length=settings.otp_length
        )

        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(
                seconds=settings.otp_expires_seconds
            )
        )

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
        self.db.refresh(request)

        # Send OTP only when an email address is available.
        if channel == "email" and email:
            asyncio.run(
                self.email_service.send_otp_email(
                    to_email=email,
                    otp_code=otp,
                )
            )

        return request, otp

    def create_password_reset_otp(
        self,
        email: str,
    ):
        user = (
            self.db.query(User)
            .filter(User.email == email.lower())
            .first()
        )

        if not user:
            raise ValueError("User not found")

        self.create_otp(
            user.id,
            channel="email",
            purpose="password_reset",
            email=user.email,
        )

        return True

    def reset_password(
        self,
        email: str,
        otp: str,
        new_password: str,
    ):
        user = (
            self.db.query(User)
            .filter(User.email == email.lower())
            .first()
        )

        if not user:
            raise ValueError("Invalid email or OTP")

        verified = self.verify_otp_once(
            user.id,
            otp,
            purpose="password_reset",
        )

        if not verified:
            raise ValueError("Invalid or expired OTP")

        user.password_hash = hash_password(new_password)

        self.db.commit()

        return True

    def verify_otp_once(
        self,
        user_id: str,
        otp: str,
        purpose: str = "login",
    ):
        pending = (
            self.db.query(OTPRequest)
            .filter(OTPRequest.user_id == user_id)
            .filter(OTPRequest.purpose == purpose)
            .filter(OTPRequest.is_active == True)
            .filter(OTPRequest.used_at.is_(None))
            .filter(
                OTPRequest.expires_at
                >= datetime.now(timezone.utc)
            )
            .order_by(
                OTPRequest.created_at.desc()
            )
            .first()
        )

        if not pending:
            return False

        if pending.attempts >= settings.otp_attempt_limit:
            return False

        verified = verify_password(
            otp,
            pending.otp_hash,
        )

        if not verified:
            pending.attempts += 1
            self.db.commit()
            return False

        pending.used_at = datetime.now(timezone.utc)
        pending.is_active = False

        user = (
            self.db.query(User)
            .filter(User.id == user_id)
            .first()
        )

        if not user:
            return False

        # Only registration/login OTP verifies the user.
        if purpose == "login":
            user.is_verified = True

        self.db.commit()

        # Welcome email is only sent after registration verification.
        if purpose == "login":
            try:
                asyncio.run(
                    self.email_service.send_welcome_email(
                        to_email=user.email,
                        user_name=user.name,
                    )
                )
            except Exception as exc:
                print(
                    f"Welcome email could not be sent to "
                    f"{user.email}: {exc}"
                )

        return True
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import uuid
import jwt

from app.core.config import settings


class JWTService:
    @staticmethod
    def create_access_token(subject: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": subject,
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int(
                (now + timedelta(
                    minutes=settings.jwt_access_token_expire_minutes
                )).timestamp()
            ),
        }
        return jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

    @staticmethod
    def create_refresh_token(subject: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": subject,
            "type": "refresh",
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int(
                (now + timedelta(
                    days=settings.jwt_refresh_token_expire_days
                )).timestamp()
            ),
        }
        return jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

    @staticmethod
    def validate_access_token(token: str) -> Dict[str, Any]:
        payload = JWTService.decode_token(token)
        if payload.get("type") != "access":
            raise jwt.InvalidTokenError("invalid token type")
        return payload

    @staticmethod
    def validate_refresh_token(token: str) -> Dict[str, Any]:
        payload = JWTService.decode_token(token)
        if payload.get("type") != "refresh":
            raise jwt.InvalidTokenError("invalid token type")
        return payload
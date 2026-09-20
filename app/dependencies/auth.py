from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt import InvalidTokenError

from app.core.config import settings
from app.core.jwt_service import JWTService
from app.db.models.user import User

from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user_token(creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return creds.credentials


def get_current_user_from_access_token(
    token: str = Depends(get_current_user_token),
    db: Session = Depends(get_db),
) -> dict:
    try:
        payload = JWTService.validate_access_token(token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Verification enforcement is opt-in (see settings.require_verified_user).
    # The OTP architecture stays in place; only the gate is flag-controlled so
    # existing unverified accounts are not locked out of protected endpoints.
    if settings.require_verified_user and not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not verified",
        )

    return payload

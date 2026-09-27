from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import uuid4
import hashlib

from app.db.session import get_db
from app.db.models.user import User

from app.core.jwt_service import JWTService

from app.dependencies.auth import (
    get_current_user_from_access_token,
)

from app.services.auth_service import AuthService
from app.services.token_service import TokenService

from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    OTPVerifyRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    RefreshTokenRequest,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)


@router.post("/register")
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(db)

    try:
        user = service.register(
            payload.name,
            str(payload.email),
            payload.password,
            payload.phone,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    access_token = JWTService.create_access_token(user.id)
    refresh_token = JWTService.create_refresh_token(user.id)

    TokenService(db).store_refresh_token(
        user_id=user.id,
        token=refresh_token,
        family_id=str(uuid4()),
    )

    db.commit()

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
        },
    }


@router.post("/login")
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(db)

    try:
        data = service.login(
            str(payload.email),
            payload.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
        ) from exc

    return data


@router.get("/me")
def current_user(
    payload: dict = Depends(
        get_current_user_from_access_token
    ),
):
    return payload


@router.post("/refresh")
def refresh_token(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    try:
        token_payload = JWTService.validate_refresh_token(
            payload.refresh_token
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = token_payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    new_refresh_token = TokenService(
        db
    ).rotate_refresh_token(
        payload.refresh_token
    )

    if not new_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Refresh token is revoked, expired, "
                "or not recognized"
            ),
        )

    return {
        "accessToken": JWTService.create_access_token(
            user_id
        ),
        "refreshToken": new_refresh_token,
    }


@router.post("/verify-otp")
def verify_otp(
    payload: OTPVerifyRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(db)

    user = (
        db.query(User)
        .filter(
            User.email
            == str(payload.email).lower()
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if not service.verify_otp_once(
        user.id,
        payload.otp,
        purpose="login",
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OTP",
        )

    return {
        "verified": True,
        "message": "OTP verified successfully",
    }


@router.post("/resend-otp")
def resend_otp(
    payload: OTPVerifyRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(db)

    user = (
        db.query(User)
        .filter(
            User.email
            == str(payload.email).lower()
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if user.is_verified:
        raise HTTPException(
            status_code=400,
            detail="User is already verified",
        )

    service.create_otp(
        user.id,
        channel="email",
        purpose="login",
        email=user.email,
    )

    return {
        "message": "OTP resent successfully",
    }


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(db)

    try:
        service.create_password_reset_otp(
            str(payload.email)
        )
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return {
        "message": (
            "Password reset OTP sent successfully"
        ),
    }


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(db)

    try:
        service.reset_password(
            email=str(payload.email),
            otp=payload.otp,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "message": "Password reset successfully",
    }


@router.post("/logout")
def logout(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    token_hash = hashlib.sha256(
        payload.refresh_token.encode()
    ).hexdigest()

    TokenService(db).revoke_refresh_token(
        token_hash
    )

    return {
        "message": "Logged out successfully",
    }
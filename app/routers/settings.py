from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.models.user_preferences import UserPreferences
from app.db.session import get_db
from app.dependencies.auth import get_current_user_from_access_token
from app.schemas.settings import PreferencesUpdate, SettingsRead, SettingsUpdateResponse

router = APIRouter(prefix="/api", tags=["settings"])


def _get_current_user(db: Session, auth_payload: dict) -> User:
    user = db.query(User).filter(User.id == auth_payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _get_preferences(db: Session, user: User) -> UserPreferences:
    preferences = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()
    if not preferences:
        preferences = UserPreferences(user_id=user.id, language="English", theme_mode="light", notifications_enabled=True)
        db.add(preferences)
        db.commit()
        db.refresh(preferences)
    return preferences


def _settings_response(preferences: UserPreferences) -> dict:
    return {
        "language": preferences.language,
        "themeMode": preferences.theme_mode,
        "notificationsEnabled": preferences.notifications_enabled,
    }


@router.get("/settings", response_model=SettingsRead)
def get_settings(
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    return _settings_response(_get_preferences(db, user))


@router.patch("/settings/preferences", response_model=SettingsUpdateResponse)
def update_settings_preferences(
    payload: PreferencesUpdate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    preferences = _get_preferences(db, user)
    updates = payload.model_dump(exclude_unset=True, by_alias=False)
    if "theme_mode" in updates:
        preferences.theme_mode = updates["theme_mode"]
    if "language" in updates:
        preferences.language = updates["language"]
    if "notifications_enabled" in updates:
        preferences.notifications_enabled = updates["notifications_enabled"]
    db.commit()
    db.refresh(preferences)
    return {"message": "Settings updated", "settings": _settings_response(preferences)}

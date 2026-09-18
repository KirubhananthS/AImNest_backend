from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.notification import Notification
from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user_from_access_token
from app.schemas.notification import NotificationRead

router = APIRouter(prefix="/api", tags=["notifications"])


def _get_current_user(db: Session, auth_payload: dict) -> User:
    user = db.query(User).filter(User.id == auth_payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _get_owned_notification(db: Session, notification_id: str, user: User) -> Notification:
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user.id,
    ).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.get("/notifications", response_model=list[NotificationRead])
def list_notifications(
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    return db.query(Notification).filter(
        Notification.user_id == user.id,
    ).order_by(Notification.created_at.desc()).all()


@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)
    notification = _get_owned_notification(db, notification_id, user)
    notification.is_read = True
    db.commit()
    return {"message": "Notification marked as read", "id": notification.id, "read": True}

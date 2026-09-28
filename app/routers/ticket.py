from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.ticket import Ticket
from app.db.models.ticket_activity import TicketActivity
from app.db.models.ticket_attempt import TicketAttempt
from app.db.models.goal import Goal
from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user_from_access_token
from app.schemas.ticket import TicketCreate, TicketRead, TicketUpdate
from app.schemas.ticket_activity import TicketActivityRead
from app.schemas.ticket_attempt import TicketAttemptCreate, TicketAttemptRead


router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _get_current_user(db: Session, auth_payload: dict) -> User:
    user = db.query(User).filter(User.id == auth_payload.get("sub")).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )

    return user


def _get_owned_ticket(
    db: Session,
    ticket_id: str,
    user: User,
) -> Ticket:
    ticket = (
        db.query(Ticket)
        .filter(
            Ticket.id == ticket_id,
            Ticket.user_id == user.id,
        )
        .first()
    )

    if not ticket:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found",
        )

    return ticket


def _clean_required(value: str, field_name: str) -> str:
    cleaned = value.strip()

    if not cleaned:
        raise HTTPException(
            status_code=422,
            detail=f"Ticket {field_name} must not be empty",
        )

    return cleaned


@router.post("", response_model=TicketRead)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)

    goal = None

    if payload.goal_id:
        goal = (
            db.query(Goal)
            .filter(
                Goal.id == payload.goal_id,
                Goal.user_id == user.id,
            )
            .first()
        )

        if not goal:
            raise HTTPException(
                status_code=404,
                detail="Goal not found",
            )

    ticket = Ticket(
        user_id=user.id,
        goal_id=payload.goal_id,
        title=_clean_required(payload.title, "title"),
        description=_clean_required(payload.description, "description"),
        category=_clean_required(payload.category, "category"),
        difficulty=payload.difficulty,
        priority=payload.priority,
        status=payload.status,
        progress=payload.progress,
        due_date=payload.due_date,
    )

    # Add ticket first so ticket.id is generated
    db.add(ticket)
    db.flush()

    # Automatically create activity for ticket creation
    activity = TicketActivity(
        ticket_id=ticket.id,
        user_id=user.id,
        action="ticket_created",
        description=f"Ticket created: {ticket.title}",
        event_metadata={
            "status": ticket.status,
            "progress": ticket.progress,
        },
    )

    db.add(activity)

    # Save both ticket and activity in the same transaction
    db.commit()

    db.refresh(ticket)

    return ticket


@router.get("", response_model=list[TicketRead])
def list_tickets(
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)

    return (
        db.query(Ticket)
        .filter(Ticket.user_id == user.id)
        .order_by(Ticket.created_at.desc())
        .all()
    )


@router.get("/{ticket_id}", response_model=TicketRead)
def get_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)

    return _get_owned_ticket(db, ticket_id, user)


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(
    ticket_id: str,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)

    ticket = _get_owned_ticket(db, ticket_id, user)

    updates = payload.model_dump(exclude_unset=True)

    for field_name in (
        "title",
        "description",
        "category",
    ):
        if field_name in updates:
            updates[field_name] = _clean_required(
                updates[field_name],
                field_name,
            )

    if "goal_id" in updates and updates["goal_id"]:
        goal = (
            db.query(Goal)
            .filter(
                Goal.id == updates["goal_id"],
                Goal.user_id == user.id,
            )
            .first()
        )

        if not goal:
            raise HTTPException(
                status_code=404,
                detail="Goal not found",
            )

    # Store old values before updating the ticket
    old_values = {}

    for field_name, new_value in updates.items():
        old_values[field_name] = getattr(ticket, field_name)

    # Update ticket
    for field_name, value in updates.items():
        setattr(ticket, field_name, value)

    ticket.updated_at = datetime.now(timezone.utc)

    # Create activity for every changed field
    for field_name, new_value in updates.items():
        old_value = old_values[field_name]

        if old_value == new_value:
            continue

        if field_name == "status":
            action = "status_changed"
            description = (
                f"Ticket status changed from "
                f"{old_value} to {new_value}"
            )

        elif field_name == "progress":
            action = "progress_updated"
            description = (
                f"Ticket progress changed from "
                f"{old_value}% to {new_value}%"
            )

        elif field_name == "priority":
            action = "priority_changed"
            description = (
                f"Ticket priority changed from "
                f"{old_value} to {new_value}"
            )

        elif field_name == "due_date":
            action = "due_date_changed"
            description = "Ticket due date updated"

        elif field_name == "title":
            action = "title_changed"
            description = "Ticket title updated"

        elif field_name == "description":
            action = "description_changed"
            description = "Ticket description updated"

        elif field_name == "category":
            action = "category_changed"
            description = "Ticket category updated"

        elif field_name == "difficulty":
            action = "difficulty_changed"
            description = "Ticket difficulty changed"

        elif field_name == "goal_id":
            action = "goal_changed"
            description = "Ticket goal updated"

        else:
            action = f"{field_name}_changed"
            description = f"Ticket {field_name} updated"

        activity = TicketActivity(
            ticket_id=ticket.id,
            user_id=user.id,
            action=action,
            description=description,
            event_metadata={
                "field": field_name,
                "old_value": old_value,
                "new_value": new_value,
            },
        )

        db.add(activity)

    db.commit()
    db.refresh(ticket)

    return ticket


@router.delete("/{ticket_id}")
def delete_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)

    ticket = _get_owned_ticket(db, ticket_id, user)

    db.delete(ticket)
    db.commit()

    return {
        "message": "Ticket deleted",
    }




@router.get(
    "/{ticket_id}/attempts",
    response_model=list[TicketAttemptRead],
)
def list_ticket_attempts(
    ticket_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)

    ticket = _get_owned_ticket(db, ticket_id, user)

    return (
        db.query(TicketAttempt)
        .filter(
            TicketAttempt.ticket_id == ticket.id,
            TicketAttempt.user_id == user.id,
        )
        .order_by(TicketAttempt.attempt_number.asc())
        .all()
    )

@router.get(
    "/{ticket_id}/activities",
    response_model=list[TicketActivityRead],
)
def list_ticket_activities(
    ticket_id: str,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_user_from_access_token),
):
    user = _get_current_user(db, auth_payload)

    ticket = _get_owned_ticket(db, ticket_id, user)

    return (
        db.query(TicketActivity)
        .filter(
            TicketActivity.ticket_id == ticket.id,
            TicketActivity.user_id == user.id,
        )
        .order_by(TicketActivity.created_at.asc())
        .all()
    )
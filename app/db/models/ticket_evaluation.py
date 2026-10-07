from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TicketEvaluation(Base):
    __tablename__ = "ticket_evaluations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    attempt_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ticket_attempts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    feedback: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    root_cause_quality: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    solution_quality: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    evidence_quality: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    next_action: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(),
    )

    attempt = relationship(
        "TicketAttempt",
    )
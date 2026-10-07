from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LearnerSkill(Base):
    __tablename__ = "learner_skills"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    skill: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    level: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="beginner",
    )

    experience_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    evidence_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    last_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User")
    
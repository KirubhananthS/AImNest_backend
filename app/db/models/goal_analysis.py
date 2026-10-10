from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GoalAnalysis(Base):
    __tablename__ = "goal_analyses"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    goal_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("goals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    learner_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    skill_gaps: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    topics: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    recommended_difficulty: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="beginner",
    )

    learning_sequence: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    expectations: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    goal = relationship("Goal")

"""User model for authentication and user management."""

from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.career import CareerAnalytics, CareerProfile, CareerTurningPoint, JobEntry


class User(BaseModel):
    """User model for authentication and user management."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    # Relationships
    career_profiles: Mapped[List["CareerProfile"]] = relationship(
        "CareerProfile",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    job_entries: Mapped[List["JobEntry"]] = relationship(
        "JobEntry",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    career_analytics: Mapped["CareerAnalytics"] = relationship(
        "CareerAnalytics",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    career_turning_points: Mapped[List["CareerTurningPoint"]] = relationship(
        "CareerTurningPoint",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"

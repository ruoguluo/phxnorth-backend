"""Career profile models for CV storage and analytics."""

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class ProfileSource(str, enum.Enum):
    """Source of the career profile data."""

    UPLOAD = "upload"
    LINKEDIN = "linkedin"
    MANUAL = "manual"
    PASTE = "paste"


class SeniorityLevel(str, enum.Enum):
    """Seniority level of a job role."""

    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    PRINCIPAL = "principal"
    EXECUTIVE = "executive"


class EmploymentType(str, enum.Enum):
    """Type of employment."""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    FREELANCE = "freelance"
    INTERNSHIP = "internship"


class TurningPointType(str, enum.Enum):
    """Type of career turning point."""

    PROMOTION = "promotion"
    LATERAL_MOVE = "lateral_move"
    CAREER_CHANGE = "career_change"
    INDUSTRY_SWITCH = "industry_switch"
    STARTUP_FOUNDED = "startup_founded"
    STARTUP_EXIT = "startup_exit"
    LAYOFF = "layoff"
    SABBATICAL = "sabbatical"
    RETURN_TO_WORK = "return_to_work"
    RETIREMENT = "retirement"


class CareerProfile(BaseModel):
    """Raw CV storage and parsing metadata."""

    __tablename__ = "career_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[ProfileSource] = mapped_column(
        String(20),
        nullable=False,
    )
    raw_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    raw_file_s3_key: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    parsed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    parser_version: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="career_profiles")
    job_entries: Mapped[list["JobEntry"]] = relationship(
        "JobEntry",
        back_populates="career_profile",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<CareerProfile(id={self.id}, user_id={self.user_id}, source={self.source})>"


class JobEntry(BaseModel):
    """Individual job roles within a career profile."""

    __tablename__ = "job_entries"

    career_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("career_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    job_title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    industry: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    functional_area: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    seniority_level: Mapped[Optional[SeniorityLevel]] = mapped_column(
        String(50),
        nullable=True,
    )
    employment_type: Mapped[Optional[EmploymentType]] = mapped_column(
        String(50),
        nullable=True,
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    end_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    duration_months: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    description_raw: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    sequence_index: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Relationships
    career_profile: Mapped["CareerProfile"] = relationship(
        "CareerProfile",
        back_populates="job_entries",
    )
    user: Mapped["User"] = relationship("User", back_populates="job_entries")
    turning_points: Mapped[list["CareerTurningPoint"]] = relationship(
        "CareerTurningPoint",
        back_populates="job_entry",
        cascade="all, delete-orphan",
    )

    # Hybrid properties for computed columns
    @hybrid_property
    def is_short_tenure(self) -> bool:
        """True if duration is less than 12 months."""
        if self.duration_months is None:
            return False
        return self.duration_months < 12

    @hybrid_property
    def is_current(self) -> bool:
        """True if this is the current job (no end date)."""
        return self.end_date is None

    def __repr__(self) -> str:
        return f"<JobEntry(id={self.id}, company={self.company_name}, title={self.job_title})>"


class CareerAnalytics(BaseModel):
    """Computed career metrics and analytics."""

    __tablename__ = "career_analytics"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    total_roles: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    short_tenure_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    short_tenure_rate: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    avg_tenure_months: Mapped[Optional[float]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    career_span_years: Mapped[Optional[float]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    transition_frequency: Mapped[Optional[float]] = mapped_column(
        Numeric(6, 4),
        nullable=True,
    )
    cross_industry_transitions: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    upward_moves: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    lateral_moves: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    downward_moves: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    industry_diversity_score: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    functional_diversity_score: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    longest_tenure_months: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    career_volatility_score: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="career_analytics")

    def __repr__(self) -> str:
        return f"<CareerAnalytics(user_id={self.user_id}, total_roles={self.total_roles})>"


class CareerTurningPoint(BaseModel):
    """Career decision points and transitions."""

    __tablename__ = "career_turning_points"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    point_type: Mapped[TurningPointType] = mapped_column(
        String(50),
        nullable=False,
    )
    inferred_motive: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    context_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    confidence: Mapped[Optional[float]] = mapped_column(
        Numeric(4, 3),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="career_turning_points")
    job_entry: Mapped[Optional["JobEntry"]] = relationship(
        "JobEntry",
        back_populates="turning_points",
    )

    def __repr__(self) -> str:
        return f"<CareerTurningPoint(id={self.id}, type={self.point_type}, confidence={self.confidence})>"

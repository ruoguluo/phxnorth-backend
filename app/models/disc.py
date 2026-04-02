"""DISC Engine models for personality profiling and risk assessment."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class DISCTrait(str, enum.Enum):
    """DISC personality traits."""

    D = "D"  # Dominance
    I = "I"  # Influence
    S = "S"  # Steadiness
    C = "C"  # Conscientiousness


class SeverityLevel(str, enum.Enum):
    """Risk severity levels."""

    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"


class RiskCategory(str, enum.Enum):
    """Risk assessment categories."""

    CAREER_VOLATILITY = "career_volatility"
    JOB_HOPPING = "job_hopping"
    SKILL_STAGNATION = "skill_stagnation"
    NETWORK_ISOLATION = "network_isolation"
    COMMUNICATION_RISK = "communication_risk"
    LEADERSHIP_GAP = "leadership_gap"
    ADAPTABILITY_CONCERN = "adaptability_concern"
    STRESS_TOLERANCE = "stress_tolerance"


class ShiftType(str, enum.Enum):
    """Types of DISC profile shifts."""

    STABLE = "stable"
    GRADUAL = "gradual"
    SIGNIFICANT = "significant"
    DRAMATIC = "dramatic"
    REVERSAL = "reversal"


class DISCProfile(BaseModel):
    """DISC score snapshots for personality profiling."""

    __tablename__ = "disc_profiles"
    __table_args__ = (
        {"comment": "DISC personality profiles with temporal analysis"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    d_score: Mapped[float] = mapped_column(
        Numeric(5, 1),
        nullable=False,
        comment="Dominance score (0-100)",
    )
    i_score: Mapped[float] = mapped_column(
        Numeric(5, 1),
        nullable=False,
        comment="Influence score (0-100)",
    )
    s_score: Mapped[float] = mapped_column(
        Numeric(5, 1),
        nullable=False,
        comment="Steadiness score (0-100)",
    )
    c_score: Mapped[float] = mapped_column(
        Numeric(5, 1),
        nullable=False,
        comment="Conscientiousness score (0-100)",
    )
    dominant: Mapped[Optional[DISCTrait]] = mapped_column(
        String(1),
        nullable=True,
        comment="Primary DISC trait",
    )
    secondary: Mapped[Optional[DISCTrait]] = mapped_column(
        String(1),
        nullable=True,
        comment="Secondary DISC trait",
    )
    confidence: Mapped[Optional[float]] = mapped_column(
        Numeric(4, 3),
        nullable=True,
        comment="Confidence score (0.000-1.000)",
    )
    signal_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of behavioral signals used",
    )
    contradiction_score: Mapped[Optional[float]] = mapped_column(
        Numeric(4, 3),
        nullable=True,
        comment="Internal consistency score (0.000-1.000)",
    )
    shift_magnitude: Mapped[Optional[float]] = mapped_column(
        Numeric(4, 3),
        nullable=True,
        comment="Magnitude of change from previous profile",
    )
    shift_type: Mapped[Optional[ShiftType]] = mapped_column(
        String(30),
        nullable=True,
        comment="Classification of profile change",
    )
    model_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Version of the DISC model used",
    )
    window_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Analysis window in days (7 | 30 | 90 | 365 | null=lifetime)",
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<DISCProfile(id={self.id}, user_id={self.user_id}, "
            f"dominant={self.dominant}, window={self.window_days}d)>"
        )


class PreferenceProfile(BaseModel):
    """Preference indexes for behavioral analysis."""

    __tablename__ = "preference_profiles"
    __table_args__ = (
        {"comment": "User preference profiles derived from DISC analysis"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stability_vs_growth: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 3),
        nullable=True,
        comment="Preference for stability (-1.0) vs growth (1.0)",
    )
    conservative_vs_aggressive_risk: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 3),
        nullable=True,
        comment="Risk tolerance: conservative (-1.0) vs aggressive (1.0)",
    )
    control_vs_collaboration: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 3),
        nullable=True,
        comment="Work style: control (-1.0) vs collaboration (1.0)",
    )
    short_term_vs_long_term: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 3),
        nullable=True,
        comment="Time horizon: short-term (-1.0) vs long-term (1.0)",
    )
    consistency_score: Mapped[Optional[float]] = mapped_column(
        Numeric(4, 3),
        nullable=True,
        comment="Consistency of preferences over time (0.000-1.000)",
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<PreferenceProfile(id={self.id}, user_id={self.user_id})>"


class RiskAssessment(BaseModel):
    """Risk category scores for user evaluation."""

    __tablename__ = "risk_assessments"
    __table_args__ = (
        {"comment": "Risk assessments by category"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[RiskCategory] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Risk category being assessed",
    )
    score: Mapped[float] = mapped_column(
        Numeric(4, 3),
        nullable=False,
        comment="Risk score (0.000-1.000)",
    )
    severity: Mapped[SeverityLevel] = mapped_column(
        String(10),
        nullable=False,
        comment="Severity classification",
    )
    evidence: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Supporting evidence for the assessment",
    )
    is_flagged: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether this risk requires attention",
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<RiskAssessment(id={self.id}, user_id={self.user_id}, "
            f"category={self.category}, severity={self.severity})>"
        )


class RedFlagEvent(BaseModel):
    """Immutable audit trail for significant risk events.

    Note: RedFlagEvent does not use updated_at from BaseModel as events
    are immutable once created. Only resolved_at and resolved status can change.
    """

    __tablename__ = "red_flag_events"
    __table_args__ = (
        {"comment": "Immutable audit trail for risk events"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    flag_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
        comment="Type of red flag event",
    )
    severity: Mapped[SeverityLevel] = mapped_column(
        String(10),
        nullable=False,
        comment="Severity of the red flag",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed description of the event",
    )
    event_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata",  # Column name in DB matches schema
        JSONB,
        nullable=True,
        comment="Additional context and data",
    )
    resolved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether the red flag has been addressed",
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the red flag was resolved",
    )

    # Note: created_at is inherited from BaseModel
    # updated_at is inherited but should not be used (events are immutable)

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<RedFlagEvent(id={self.id}, user_id={self.user_id}, "
            f"flag_type={self.flag_type}, severity={self.severity}, "
            f"resolved={self.resolved})>"
        )

"""Tests for DISC models."""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.disc import (
    DISCProfile,
    DISCTrait,
    PreferenceProfile,
    RedFlagEvent,
    RiskAssessment,
    RiskCategory,
    SeverityLevel,
    ShiftType,
)
from app.models.user import User


class TestDISCProfileInstantiation:
    """Test DISCProfile model instantiation."""

    async def test_disc_profile_can_be_created(self, db_session: AsyncSession, sample_user_data, sample_disc_profile_data):
        """Test that a DISC profile can be created."""
        # Create user first
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        # Create DISC profile
        profile = DISCProfile(
            user_id=user.id,
            **sample_disc_profile_data,
        )
        db_session.add(profile)
        await db_session.commit()

        assert profile.id is not None
        assert isinstance(profile.id, uuid.UUID)
        assert profile.user_id == user.id
        assert profile.d_score == 75.5
        assert profile.i_score == 60.0
        assert profile.s_score == 45.5
        assert profile.c_score == 80.0
        assert profile.dominant == DISCTrait.D
        assert profile.secondary == DISCTrait.C

    async def test_disc_profile_has_timestamps(self, db_session: AsyncSession, sample_user_data):
        """Test that DISC profile has timestamps."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = DISCProfile(
            user_id=user.id,
            d_score=50.0,
            i_score=50.0,
            s_score=50.0,
            c_score=50.0,
        )
        db_session.add(profile)
        await db_session.commit()

        assert profile.created_at is not None
        assert profile.updated_at is not None
        assert isinstance(profile.created_at, datetime)

    async def test_disc_profile_model_version_defaults(self, db_session: AsyncSession, sample_user_data):
        """Test that model_version defaults to '1.0'."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = DISCProfile(
            user_id=user.id,
            d_score=50.0,
            i_score=50.0,
            s_score=50.0,
            c_score=50.0,
        )
        db_session.add(profile)
        await db_session.commit()

        assert profile.model_version == "1.0"


class TestDISCProfileConstraints:
    """Test DISCProfile model constraints."""

    async def test_user_id_is_required(self, db_session: AsyncSession):
        """Test that user_id cannot be null."""
        profile = DISCProfile(
            user_id=None,
            d_score=50.0,
            i_score=50.0,
            s_score=50.0,
            c_score=50.0,
        )
        db_session.add(profile)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    async def test_score_fields_are_required(self, db_session: AsyncSession, sample_user_data):
        """Test that score fields cannot be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = DISCProfile(
            user_id=user.id,
            d_score=None,
            i_score=50.0,
            s_score=50.0,
            c_score=50.0,
        )
        db_session.add(profile)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    async def test_optional_fields_can_be_null(self, db_session: AsyncSession, sample_user_data):
        """Test that optional fields can be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = DISCProfile(
            user_id=user.id,
            d_score=50.0,
            i_score=50.0,
            s_score=50.0,
            c_score=50.0,
            dominant=None,
            secondary=None,
            confidence=None,
            signal_count=None,
            contradiction_score=None,
            shift_magnitude=None,
            shift_type=None,
            window_days=None,
        )
        db_session.add(profile)
        await db_session.commit()

        assert profile.dominant is None
        assert profile.secondary is None


class TestDISCProfileEnumValidation:
    """Test DISCProfile enum validation."""

    async def test_disc_trait_enum_values(self, db_session: AsyncSession, sample_user_data):
        """Test that DISCTrait enum values work correctly."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        traits = [
            (DISCTrait.D, DISCTrait.I),
            (DISCTrait.I, DISCTrait.S),
            (DISCTrait.S, DISCTrait.C),
            (DISCTrait.C, DISCTrait.D),
        ]

        for dominant, secondary in traits:
            profile = DISCProfile(
                user_id=user.id,
                d_score=50.0,
                i_score=50.0,
                s_score=50.0,
                c_score=50.0,
                dominant=dominant,
                secondary=secondary,
            )
            db_session.add(profile)

        await db_session.commit()

        result = await db_session.execute(
            select(DISCProfile).where(DISCProfile.user_id == user.id)
        )
        profiles = result.scalars().all()
        assert len(profiles) == 4

    async def test_shift_type_enum_values(self, db_session: AsyncSession, sample_user_data):
        """Test that ShiftType enum values work correctly."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        shift_types = [
            ShiftType.STABLE,
            ShiftType.GRADUAL,
            ShiftType.SIGNIFICANT,
            ShiftType.DRAMATIC,
            ShiftType.REVERSAL,
        ]

        for shift_type in shift_types:
            profile = DISCProfile(
                user_id=user.id,
                d_score=50.0,
                i_score=50.0,
                s_score=50.0,
                c_score=50.0,
                shift_type=shift_type,
            )
            db_session.add(profile)

        await db_session.commit()

        result = await db_session.execute(
            select(DISCProfile).where(DISCProfile.user_id == user.id)
        )
        profiles = result.scalars().all()
        assert len(profiles) == 5


class TestPreferenceProfileInstantiation:
    """Test PreferenceProfile model instantiation."""

    async def test_preference_profile_can_be_created(self, db_session: AsyncSession, sample_user_data, sample_preference_profile_data):
        """Test that a preference profile can be created."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = PreferenceProfile(
            user_id=user.id,
            **sample_preference_profile_data,
        )
        db_session.add(profile)
        await db_session.commit()

        assert profile.id is not None
        assert profile.user_id == user.id
        assert profile.stability_vs_growth == 0.5
        assert profile.conservative_vs_aggressive_risk == -0.3

    async def test_preference_profile_has_timestamps(self, db_session: AsyncSession, sample_user_data):
        """Test that preference profile has timestamps."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = PreferenceProfile(
            user_id=user.id,
        )
        db_session.add(profile)
        await db_session.commit()

        assert profile.created_at is not None
        assert profile.updated_at is not None

    async def test_preference_profile_all_fields_optional(self, db_session: AsyncSession, sample_user_data):
        """Test that all preference fields are optional."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = PreferenceProfile(
            user_id=user.id,
            stability_vs_growth=None,
            conservative_vs_aggressive_risk=None,
            control_vs_collaboration=None,
            short_term_vs_long_term=None,
            consistency_score=None,
        )
        db_session.add(profile)
        await db_session.commit()

        assert profile.stability_vs_growth is None
        assert profile.consistency_score is None


class TestRiskAssessmentInstantiation:
    """Test RiskAssessment model instantiation."""

    async def test_risk_assessment_can_be_created(self, db_session: AsyncSession, sample_user_data, sample_risk_assessment_data):
        """Test that a risk assessment can be created."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        assessment = RiskAssessment(
            user_id=user.id,
            **sample_risk_assessment_data,
        )
        db_session.add(assessment)
        await db_session.commit()

        assert assessment.id is not None
        assert assessment.user_id == user.id
        assert assessment.category == RiskCategory.CAREER_VOLATILITY
        assert assessment.score == 0.65
        assert assessment.severity == SeverityLevel.YELLOW
        assert assessment.is_flagged is True

    async def test_risk_assessment_has_timestamps(self, db_session: AsyncSession, sample_user_data):
        """Test that risk assessment has timestamps."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        assessment = RiskAssessment(
            user_id=user.id,
            category=RiskCategory.JOB_HOPPING,
            score=0.5,
            severity=SeverityLevel.GREEN,
        )
        db_session.add(assessment)
        await db_session.commit()

        assert assessment.created_at is not None
        assert assessment.updated_at is not None

    async def test_risk_assessment_is_flagged_defaults_to_false(self, db_session: AsyncSession, sample_user_data):
        """Test that is_flagged defaults to False."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        assessment = RiskAssessment(
            user_id=user.id,
            category=RiskCategory.JOB_HOPPING,
            score=0.5,
            severity=SeverityLevel.GREEN,
        )
        db_session.add(assessment)
        await db_session.commit()

        assert assessment.is_flagged is False


class TestRiskAssessmentEnumValidation:
    """Test RiskAssessment enum validation."""

    async def test_risk_category_enum_values(self, db_session: AsyncSession, sample_user_data):
        """Test that RiskCategory enum values work correctly."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        categories = [
            RiskCategory.CAREER_VOLATILITY,
            RiskCategory.JOB_HOPPING,
            RiskCategory.SKILL_STAGNATION,
            RiskCategory.NETWORK_ISOLATION,
            RiskCategory.COMMUNICATION_RISK,
            RiskCategory.LEADERSHIP_GAP,
            RiskCategory.ADAPTABILITY_CONCERN,
            RiskCategory.STRESS_TOLERANCE,
        ]

        for category in categories:
            assessment = RiskAssessment(
                user_id=user.id,
                category=category,
                score=0.5,
                severity=SeverityLevel.GREEN,
            )
            db_session.add(assessment)

        await db_session.commit()

        result = await db_session.execute(
            select(RiskAssessment).where(RiskAssessment.user_id == user.id)
        )
        assessments = result.scalars().all()
        assert len(assessments) == 8

    async def test_severity_level_enum_values(self, db_session: AsyncSession, sample_user_data):
        """Test that SeverityLevel enum values work correctly."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        severities = [
            SeverityLevel.GREEN,
            SeverityLevel.YELLOW,
            SeverityLevel.ORANGE,
            SeverityLevel.RED,
        ]

        for severity in severities:
            assessment = RiskAssessment(
                user_id=user.id,
                category=RiskCategory.CAREER_VOLATILITY,
                score=0.5,
                severity=severity,
            )
            db_session.add(assessment)

        await db_session.commit()

        result = await db_session.execute(
            select(RiskAssessment).where(RiskAssessment.user_id == user.id)
        )
        assessments = result.scalars().all()
        assert len(assessments) == 4


class TestRiskAssessmentJSONField:
    """Test RiskAssessment JSON field handling."""

    async def test_evidence_stores_complex_json(self, db_session: AsyncSession, sample_user_data):
        """Test that evidence can store complex JSON data."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        complex_evidence = {
            "job_changes": [
                {"company": "Tech Corp", "duration": 6},
                {"company": "Startup Inc", "duration": 8},
            ],
            "avg_tenure": 7.0,
            "flags": ["short_tenure", "frequent_switching"],
        }

        assessment = RiskAssessment(
            user_id=user.id,
            category=RiskCategory.JOB_HOPPING,
            score=0.75,
            severity=SeverityLevel.ORANGE,
            evidence=complex_evidence,
        )
        db_session.add(assessment)
        await db_session.commit()

        await db_session.refresh(assessment)
        assert assessment.evidence == complex_evidence

    async def test_evidence_can_be_null(self, db_session: AsyncSession, sample_user_data):
        """Test that evidence can be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        assessment = RiskAssessment(
            user_id=user.id,
            category=RiskCategory.JOB_HOPPING,
            score=0.5,
            severity=SeverityLevel.GREEN,
            evidence=None,
        )
        db_session.add(assessment)
        await db_session.commit()

        assert assessment.evidence is None


class TestRedFlagEventInstantiation:
    """Test RedFlagEvent model instantiation."""

    async def test_red_flag_event_can_be_created(self, db_session: AsyncSession, sample_user_data, sample_red_flag_event_data):
        """Test that a red flag event can be created."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = RedFlagEvent(
            user_id=user.id,
            **sample_red_flag_event_data,
        )
        db_session.add(event)
        await db_session.commit()

        assert event.id is not None
        assert event.user_id == user.id
        assert event.flag_type == "high_volatility"
        assert event.severity == SeverityLevel.ORANGE
        assert event.resolved is False

    async def test_red_flag_event_has_created_at(self, db_session: AsyncSession, sample_user_data):
        """Test that red flag event has created_at timestamp."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = RedFlagEvent(
            user_id=user.id,
            flag_type="test_flag",
            severity=SeverityLevel.GREEN,
        )
        db_session.add(event)
        await db_session.commit()

        assert event.created_at is not None
        assert isinstance(event.created_at, datetime)

    async def test_red_flag_event_resolved_defaults_to_false(self, db_session: AsyncSession, sample_user_data):
        """Test that resolved defaults to False."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = RedFlagEvent(
            user_id=user.id,
            flag_type="test_flag",
            severity=SeverityLevel.GREEN,
        )
        db_session.add(event)
        await db_session.commit()

        assert event.resolved is False

    async def test_red_flag_event_resolved_at_can_be_null(self, db_session: AsyncSession, sample_user_data):
        """Test that resolved_at can be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = RedFlagEvent(
            user_id=user.id,
            flag_type="test_flag",
            severity=SeverityLevel.GREEN,
            resolved_at=None,
        )
        db_session.add(event)
        await db_session.commit()

        assert event.resolved_at is None


class TestRedFlagEventJSONField:
    """Test RedFlagEvent JSON field handling."""

    async def test_event_metadata_stores_complex_json(self, db_session: AsyncSession, sample_user_data):
        """Test that event_metadata can store complex JSON data."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        complex_metadata = {
            "triggered_by": "career_analysis",
            "threshold": 0.8,
            "details": {
                "positions": 5,
                "companies": ["A Corp", "B Inc", "C Ltd"],
            },
        }

        event = RedFlagEvent(
            user_id=user.id,
            flag_type="high_volatility",
            severity=SeverityLevel.ORANGE,
            event_metadata=complex_metadata,
        )
        db_session.add(event)
        await db_session.commit()

        await db_session.refresh(event)
        assert event.event_metadata == complex_metadata

    async def test_event_metadata_can_be_null(self, db_session: AsyncSession, sample_user_data):
        """Test that event_metadata can be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = RedFlagEvent(
            user_id=user.id,
            flag_type="test_flag",
            severity=SeverityLevel.GREEN,
            event_metadata=None,
        )
        db_session.add(event)
        await db_session.commit()

        assert event.event_metadata is None


class TestRedFlagEventConstraints:
    """Test RedFlagEvent model constraints."""

    async def test_flag_type_is_required(self, db_session: AsyncSession, sample_user_data):
        """Test that flag_type cannot be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = RedFlagEvent(
            user_id=user.id,
            flag_type=None,
            severity=SeverityLevel.GREEN,
        )
        db_session.add(event)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    async def test_severity_is_required(self, db_session: AsyncSession, sample_user_data):
        """Test that severity cannot be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = RedFlagEvent(
            user_id=user.id,
            flag_type="test_flag",
            severity=None,
        )
        db_session.add(event)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()


class TestDISCModelRepresentation:
    """Test DISC model string representations."""

    async def test_disc_profile_repr(self, db_session: AsyncSession, sample_user_data):
        """Test DISCProfile __repr__ method."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = DISCProfile(
            user_id=user.id,
            d_score=75.5,
            i_score=60.0,
            s_score=45.5,
            c_score=80.0,
            dominant=DISCTrait.D,
            window_days=30,
        )
        db_session.add(profile)
        await db_session.commit()

        repr_str = repr(profile)
        assert "DISCProfile" in repr_str
        assert str(profile.id) in repr_str
        assert "D" in repr_str

    async def test_preference_profile_repr(self, db_session: AsyncSession, sample_user_data):
        """Test PreferenceProfile __repr__ method."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = PreferenceProfile(
            user_id=user.id,
            stability_vs_growth=0.5,
        )
        db_session.add(profile)
        await db_session.commit()

        repr_str = repr(profile)
        assert "PreferenceProfile" in repr_str
        assert str(user.id) in repr_str

    async def test_risk_assessment_repr(self, db_session: AsyncSession, sample_user_data):
        """Test RiskAssessment __repr__ method."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        assessment = RiskAssessment(
            user_id=user.id,
            category=RiskCategory.CAREER_VOLATILITY,
            score=0.65,
            severity=SeverityLevel.YELLOW,
        )
        db_session.add(assessment)
        await db_session.commit()

        repr_str = repr(assessment)
        assert "RiskAssessment" in repr_str
        assert str(user.id) in repr_str
        assert "yellow" in repr_str

    async def test_red_flag_event_repr(self, db_session: AsyncSession, sample_user_data):
        """Test RedFlagEvent __repr__ method."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = RedFlagEvent(
            user_id=user.id,
            flag_type="high_volatility",
            severity=SeverityLevel.ORANGE,
            resolved=False,
        )
        db_session.add(event)
        await db_session.commit()

        repr_str = repr(event)
        assert "RedFlagEvent" in repr_str
        assert str(event.id) in repr_str
        assert "False" in repr_str

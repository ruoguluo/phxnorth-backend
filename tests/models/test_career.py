"""Tests for Career models."""

import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career import (
    CareerAnalytics,
    CareerProfile,
    CareerTurningPoint,
    EmploymentType,
    JobEntry,
    ProfileSource,
    SeniorityLevel,
    TurningPointType,
)
from app.models.user import User


class TestCareerProfileInstantiation:
    """Test CareerProfile model instantiation."""

    async def test_career_profile_can_be_created(self, db_session: AsyncSession, sample_user_data, sample_career_profile_data):
        """Test that a career profile can be created."""
        # Create user first
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        # Create career profile
        profile = CareerProfile(user_id=user.id, **sample_career_profile_data)
        db_session.add(profile)
        await db_session.commit()

        assert profile.id is not None
        assert isinstance(profile.id, uuid.UUID)
        assert profile.user_id == user.id
        assert profile.source == ProfileSource.UPLOAD
        assert profile.raw_text == sample_career_profile_data["raw_text"]

    async def test_career_profile_has_timestamps(self, db_session: AsyncSession, sample_user_data):
        """Test that career profile has timestamps."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = CareerProfile(
            user_id=user.id,
            source=ProfileSource.MANUAL,
        )
        db_session.add(profile)
        await db_session.commit()

        assert profile.created_at is not None
        assert profile.updated_at is not None
        assert isinstance(profile.created_at, datetime)


class TestCareerProfileConstraints:
    """Test CareerProfile model constraints."""

    async def test_user_id_is_required(self, db_session: AsyncSession):
        """Test that user_id cannot be null."""
        profile = CareerProfile(
            user_id=None,
            source=ProfileSource.UPLOAD,
        )
        db_session.add(profile)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    async def test_source_is_required(self, db_session: AsyncSession, sample_user_data):
        """Test that source cannot be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = CareerProfile(
            user_id=user.id,
            source=None,
        )
        db_session.add(profile)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    async def test_raw_fields_can_be_null(self, db_session: AsyncSession, sample_user_data):
        """Test that raw_text and raw_file_s3_key can be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = CareerProfile(
            user_id=user.id,
            source=ProfileSource.LINKEDIN,
            raw_text=None,
            raw_file_s3_key=None,
        )
        db_session.add(profile)
        await db_session.commit()

        assert profile.raw_text is None
        assert profile.raw_file_s3_key is None


class TestCareerProfileEnumValidation:
    """Test CareerProfile enum validation."""

    async def test_profile_source_enum_values(self, db_session: AsyncSession, sample_user_data):
        """Test that ProfileSource enum values work correctly."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        sources = [
            ProfileSource.UPLOAD,
            ProfileSource.LINKEDIN,
            ProfileSource.MANUAL,
            ProfileSource.PASTE,
        ]

        for source in sources:
            profile = CareerProfile(user_id=user.id, source=source)
            db_session.add(profile)

        await db_session.commit()

        # Verify all were saved
        result = await db_session.execute(
            select(CareerProfile).where(CareerProfile.user_id == user.id)
        )
        profiles = result.scalars().all()
        assert len(profiles) == 4


class TestJobEntryInstantiation:
    """Test JobEntry model instantiation."""

    async def test_job_entry_can_be_created(self, db_session: AsyncSession, sample_user_data, sample_career_profile_data, sample_job_entry_data):
        """Test that a job entry can be created."""
        # Create user and career profile
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = CareerProfile(user_id=user.id, **sample_career_profile_data)
        db_session.add(profile)
        await db_session.commit()

        # Create job entry
        job = JobEntry(
            career_profile_id=profile.id,
            user_id=user.id,
            **sample_job_entry_data,
        )
        db_session.add(job)
        await db_session.commit()

        assert job.id is not None
        assert job.career_profile_id == profile.id
        assert job.user_id == user.id
        assert job.company_name == sample_job_entry_data["company_name"]
        assert job.job_title == sample_job_entry_data["job_title"]

    async def test_job_entry_start_date_is_required(self, db_session: AsyncSession, sample_user_data, sample_career_profile_data):
        """Test that start_date cannot be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = CareerProfile(user_id=user.id, **sample_career_profile_data)
        db_session.add(profile)
        await db_session.commit()

        job = JobEntry(
            career_profile_id=profile.id,
            user_id=user.id,
            start_date=None,
        )
        db_session.add(job)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()


class TestJobEntryHybridProperties:
    """Test JobEntry hybrid properties."""

    async def test_is_short_tenure_true(self, db_session: AsyncSession, sample_user_data, sample_career_profile_data):
        """Test is_short_tenure returns True for short tenure."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = CareerProfile(user_id=user.id, **sample_career_profile_data)
        db_session.add(profile)
        await db_session.commit()

        job = JobEntry(
            career_profile_id=profile.id,
            user_id=user.id,
            start_date=date(2023, 1, 1),
            duration_months=6,
        )
        db_session.add(job)
        await db_session.commit()

        assert job.is_short_tenure is True

    async def test_is_short_tenure_false(self, db_session: AsyncSession, sample_user_data, sample_career_profile_data):
        """Test is_short_tenure returns False for long tenure."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = CareerProfile(user_id=user.id, **sample_career_profile_data)
        db_session.add(profile)
        await db_session.commit()

        job = JobEntry(
            career_profile_id=profile.id,
            user_id=user.id,
            start_date=date(2020, 1, 1),
            duration_months=24,
        )
        db_session.add(job)
        await db_session.commit()

        assert job.is_short_tenure is False

    async def test_is_short_tenure_none_duration(self, db_session: AsyncSession, sample_user_data, sample_career_profile_data):
        """Test is_short_tenure returns False when duration is None."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = CareerProfile(user_id=user.id, **sample_career_profile_data)
        db_session.add(profile)
        await db_session.commit()

        job = JobEntry(
            career_profile_id=profile.id,
            user_id=user.id,
            start_date=date(2020, 1, 1),
            duration_months=None,
        )
        db_session.add(job)
        await db_session.commit()

        assert job.is_short_tenure is False

    async def test_is_current_true(self, db_session: AsyncSession, sample_user_data, sample_career_profile_data):
        """Test is_current returns True when no end date."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = CareerProfile(user_id=user.id, **sample_career_profile_data)
        db_session.add(profile)
        await db_session.commit()

        job = JobEntry(
            career_profile_id=profile.id,
            user_id=user.id,
            start_date=date(2023, 1, 1),
            end_date=None,
        )
        db_session.add(job)
        await db_session.commit()

        assert job.is_current is True

    async def test_is_current_false(self, db_session: AsyncSession, sample_user_data, sample_career_profile_data):
        """Test is_current returns False when end date exists."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = CareerProfile(user_id=user.id, **sample_career_profile_data)
        db_session.add(profile)
        await db_session.commit()

        job = JobEntry(
            career_profile_id=profile.id,
            user_id=user.id,
            start_date=date(2020, 1, 1),
            end_date=date(2023, 1, 1),
        )
        db_session.add(job)
        await db_session.commit()

        assert job.is_current is False


class TestJobEntryEnumValidation:
    """Test JobEntry enum validation."""

    async def test_seniority_level_enum_values(self, db_session: AsyncSession, sample_user_data, sample_career_profile_data):
        """Test that SeniorityLevel enum values work correctly."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = CareerProfile(user_id=user.id, **sample_career_profile_data)
        db_session.add(profile)
        await db_session.commit()

        levels = [
            SeniorityLevel.ENTRY,
            SeniorityLevel.JUNIOR,
            SeniorityLevel.MID,
            SeniorityLevel.SENIOR,
            SeniorityLevel.LEAD,
            SeniorityLevel.PRINCIPAL,
            SeniorityLevel.EXECUTIVE,
        ]

        for i, level in enumerate(levels):
            job = JobEntry(
                career_profile_id=profile.id,
                user_id=user.id,
                start_date=date(2020 + i, 1, 1),
                seniority_level=level,
            )
            db_session.add(job)

        await db_session.commit()

        result = await db_session.execute(
            select(JobEntry).where(JobEntry.user_id == user.id)
        )
        jobs = result.scalars().all()
        assert len(jobs) == 7

    async def test_employment_type_enum_values(self, db_session: AsyncSession, sample_user_data, sample_career_profile_data):
        """Test that EmploymentType enum values work correctly."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = CareerProfile(user_id=user.id, **sample_career_profile_data)
        db_session.add(profile)
        await db_session.commit()

        types = [
            EmploymentType.FULL_TIME,
            EmploymentType.PART_TIME,
            EmploymentType.CONTRACT,
            EmploymentType.FREELANCE,
            EmploymentType.INTERNSHIP,
        ]

        for i, emp_type in enumerate(types):
            job = JobEntry(
                career_profile_id=profile.id,
                user_id=user.id,
                start_date=date(2020 + i, 1, 1),
                employment_type=emp_type,
            )
            db_session.add(job)

        await db_session.commit()

        result = await db_session.execute(
            select(JobEntry).where(JobEntry.user_id == user.id)
        )
        jobs = result.scalars().all()
        assert len(jobs) == 5


class TestCareerAnalyticsInstantiation:
    """Test CareerAnalytics model instantiation."""

    async def test_career_analytics_can_be_created(self, db_session: AsyncSession, sample_user_data):
        """Test that career analytics can be created."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        analytics = CareerAnalytics(
            user_id=user.id,
            total_roles=5,
            short_tenure_count=2,
            short_tenure_rate=0.4,
            avg_tenure_months=18.5,
            career_span_years=8.5,
            computed_at=datetime.utcnow(),
        )
        db_session.add(analytics)
        await db_session.commit()

        assert analytics.id is not None
        assert analytics.user_id == user.id
        assert analytics.total_roles == 5

    async def test_career_analytics_user_id_is_unique(self, db_session: AsyncSession, sample_user_data):
        """Test that user_id must be unique in career_analytics."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        analytics1 = CareerAnalytics(
            user_id=user.id,
            computed_at=datetime.utcnow(),
        )
        db_session.add(analytics1)
        await db_session.commit()

        analytics2 = CareerAnalytics(
            user_id=user.id,
            computed_at=datetime.utcnow(),
        )
        db_session.add(analytics2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()


class TestCareerTurningPointInstantiation:
    """Test CareerTurningPoint model instantiation."""

    async def test_turning_point_can_be_created(self, db_session: AsyncSession, sample_user_data, sample_career_profile_data):
        """Test that a turning point can be created."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = CareerProfile(user_id=user.id, **sample_career_profile_data)
        db_session.add(profile)
        await db_session.commit()

        job = JobEntry(
            career_profile_id=profile.id,
            user_id=user.id,
            start_date=date(2020, 1, 1),
        )
        db_session.add(job)
        await db_session.commit()

        turning_point = CareerTurningPoint(
            user_id=user.id,
            job_entry_id=job.id,
            point_type=TurningPointType.PROMOTION,
            inferred_motive="Career growth",
            context_text="Promoted to senior role",
            confidence=0.85,
        )
        db_session.add(turning_point)
        await db_session.commit()

        assert turning_point.id is not None
        assert turning_point.user_id == user.id
        assert turning_point.point_type == TurningPointType.PROMOTION

    async def test_turning_point_job_entry_can_be_null(self, db_session: AsyncSession, sample_user_data):
        """Test that job_entry_id can be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        turning_point = CareerTurningPoint(
            user_id=user.id,
            job_entry_id=None,
            point_type=TurningPointType.CAREER_CHANGE,
        )
        db_session.add(turning_point)
        await db_session.commit()

        assert turning_point.job_entry_id is None


class TestTurningPointEnumValidation:
    """Test CareerTurningPoint enum validation."""

    async def test_turning_point_type_enum_values(self, db_session: AsyncSession, sample_user_data):
        """Test that TurningPointType enum values work correctly."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        types = [
            TurningPointType.PROMOTION,
            TurningPointType.LATERAL_MOVE,
            TurningPointType.CAREER_CHANGE,
            TurningPointType.INDUSTRY_SWITCH,
            TurningPointType.STARTUP_FOUNDED,
            TurningPointType.STARTUP_EXIT,
            TurningPointType.LAYOFF,
            TurningPointType.SABBATICAL,
            TurningPointType.RETURN_TO_WORK,
            TurningPointType.RETIREMENT,
        ]

        for point_type in types:
            turning_point = CareerTurningPoint(
                user_id=user.id,
                point_type=point_type,
            )
            db_session.add(turning_point)

        await db_session.commit()

        result = await db_session.execute(
            select(CareerTurningPoint).where(CareerTurningPoint.user_id == user.id)
        )
        points = result.scalars().all()
        assert len(points) == 10


class TestCareerModelRepresentation:
    """Test Career model string representations."""

    async def test_career_profile_repr(self, db_session: AsyncSession, sample_user_data):
        """Test CareerProfile __repr__ method."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = CareerProfile(
            user_id=user.id,
            source=ProfileSource.UPLOAD,
        )
        db_session.add(profile)
        await db_session.commit()

        repr_str = repr(profile)
        assert "CareerProfile" in repr_str
        assert str(profile.id) in repr_str

    async def test_job_entry_repr(self, db_session: AsyncSession, sample_user_data, sample_career_profile_data):
        """Test JobEntry __repr__ method."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        profile = CareerProfile(user_id=user.id, **sample_career_profile_data)
        db_session.add(profile)
        await db_session.commit()

        job = JobEntry(
            career_profile_id=profile.id,
            user_id=user.id,
            start_date=date(2020, 1, 1),
            company_name="Tech Corp",
            job_title="Developer",
        )
        db_session.add(job)
        await db_session.commit()

        repr_str = repr(job)
        assert "JobEntry" in repr_str
        assert str(job.id) in repr_str

    async def test_career_analytics_repr(self, db_session: AsyncSession, sample_user_data):
        """Test CareerAnalytics __repr__ method."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        analytics = CareerAnalytics(
            user_id=user.id,
            total_roles=5,
            computed_at=datetime.utcnow(),
        )
        db_session.add(analytics)
        await db_session.commit()

        repr_str = repr(analytics)
        assert "CareerAnalytics" in repr_str
        assert str(user.id) in repr_str

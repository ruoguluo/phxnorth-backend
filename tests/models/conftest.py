"""Test fixtures for database models."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    CareerAnalytics,
    CareerProfile,
    CareerTurningPoint,
    DISCProfile,
    EmploymentType,
    JobEntry,
    PreferenceProfile,
    ProfileSource,
    RedFlagEvent,
    RiskAssessment,
    SeniorityLevel,
    SeverityLevel,
    TurningPointType,
    User,
)


@pytest.fixture(scope="function")
def db_session():
    """Create a database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    return User(
        email="test@example.com",
        hashed_password="hashed_password_123",
        is_active=True,
        is_superuser=False,
    )


@pytest.fixture
def sample_career_profile():
    """Create a sample career profile for testing."""
    return CareerProfile(
        source=ProfileSource.UPLOAD,
        raw_text="Sample CV text",
        raw_file_s3_key="s3://bucket/cv.pdf",
        parser_version="1.0",
    )


@pytest.fixture
def sample_job_entry():
    """Create a sample job entry for testing."""
    from datetime import date

    return JobEntry(
        company_name="Tech Corp",
        job_title="Software Engineer",
        industry="Technology",
        functional_area="Engineering",
        seniority_level=SeniorityLevel.MID,
        employment_type=EmploymentType.FULL_TIME,
        start_date=date(2020, 1, 1),
        end_date=date(2023, 1, 1),
        duration_months=36,
        description_raw="Developed software",
        sequence_index=0,
    )


@pytest.fixture
def sample_career_analytics():
    """Create a sample career analytics for testing."""
    return CareerAnalytics(
        total_roles=5,
        short_tenure_count=1,
        short_tenure_rate=0.2,
        avg_tenure_months=24.5,
        career_span_years=8.5,
        transition_frequency=0.5882,
        cross_industry_transitions=2,
        upward_moves=3,
        lateral_moves=1,
        downward_moves=0,
        industry_diversity_score=0.6,
        functional_diversity_score=0.4,
        longest_tenure_months=36,
        career_volatility_score=0.3,
    )


@pytest.fixture
def sample_career_turning_point():
    """Create a sample career turning point for testing."""
    return CareerTurningPoint(
        point_type=TurningPointType.PROMOTION,
        inferred_motive="Career growth",
        context_text="Promoted to senior role",
        confidence=0.85,
    )


@pytest.fixture
def sample_disc_profile():
    """Create a sample DISC profile for testing."""
    return DISCProfile(
        d_score=75.5,
        i_score=60.0,
        s_score=45.5,
        c_score=80.0,
        dominant="C",
        secondary="D",
        confidence=0.92,
        signal_count=150,
        contradiction_score=0.15,
        shift_magnitude=0.05,
        model_version="1.0",
        window_days=30,
    )


@pytest.fixture
def sample_preference_profile():
    """Create a sample preference profile for testing."""
    return PreferenceProfile(
        stability_vs_growth=0.65,
        conservative_vs_aggressive_risk=-0.45,
        control_vs_collaboration=0.30,
        short_term_vs_long_term=0.80,
        consistency_score=0.88,
    )


@pytest.fixture
def sample_risk_assessment():
    """Create a sample risk assessment for testing."""
    return RiskAssessment(
        category="career_volatility",
        score=0.35,
        severity=SeverityLevel.YELLOW,
        evidence={"reason": "Multiple short tenures"},
        is_flagged=True,
    )


@pytest.fixture
def sample_red_flag_event():
    """Create a sample red flag event for testing."""
    return RedFlagEvent(
        flag_type="high_volatility",
        severity=SeverityLevel.ORANGE,
        description="Career shows high volatility pattern",
        event_metadata={"threshold": 0.7, "actual": 0.85},
        resolved=False,
    )

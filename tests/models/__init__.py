"""Test fixtures for database models."""

import asyncio
import uuid
from datetime import date, datetime
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base


# Use in-memory SQLite for model tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Create a database engine for testing."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    async_session = sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    async with async_session() as session:
        yield session
        # Rollback after each test
        await session.rollback()


@pytest.fixture
def sample_user_data():
    """Sample data for creating a User."""
    return {
        "email": "test@example.com",
        "hashed_password": "hashed_password_123",
        "is_active": True,
        "is_superuser": False,
    }


@pytest.fixture
def sample_career_profile_data():
    """Sample data for creating a CareerProfile."""
    return {
        "source": "upload",
        "raw_text": "Sample CV text content",
        "raw_file_s3_key": "uploads/cv_123.pdf",
        "parsed_at": datetime.utcnow(),
        "parser_version": "1.0.0",
    }


@pytest.fixture
def sample_job_entry_data():
    """Sample data for creating a JobEntry."""
    return {
        "company_name": "Tech Corp",
        "job_title": "Senior Developer",
        "industry": "Technology",
        "functional_area": "Engineering",
        "seniority_level": "senior",
        "employment_type": "full_time",
        "start_date": date(2020, 1, 1),
        "end_date": date(2023, 12, 31),
        "duration_months": 47,
        "description_raw": "Worked on various projects",
        "sequence_index": 0,
    }


@pytest.fixture
def sample_behavioral_event_data():
    """Sample data for creating a BehavioralEvent."""
    return {
        "event_type": "page_view",
        "payload": {"page": "/dashboard", "duration": 120},
        "latency_ms": 50,
        "client_type": "web",
    }


@pytest.fixture
def sample_disc_profile_data():
    """Sample data for creating a DISCProfile."""
    return {
        "d_score": 75.5,
        "i_score": 60.0,
        "s_score": 45.5,
        "c_score": 80.0,
        "dominant": "D",
        "secondary": "C",
        "confidence": 0.85,
        "signal_count": 150,
        "contradiction_score": 0.15,
        "shift_magnitude": 0.05,
        "shift_type": "stable",
        "model_version": "1.0",
        "window_days": 30,
    }


@pytest.fixture
def sample_preference_profile_data():
    """Sample data for creating a PreferenceProfile."""
    return {
        "stability_vs_growth": 0.5,
        "conservative_vs_aggressive_risk": -0.3,
        "control_vs_collaboration": 0.2,
        "short_term_vs_long_term": 0.7,
        "consistency_score": 0.85,
    }


@pytest.fixture
def sample_risk_assessment_data():
    """Sample data for creating a RiskAssessment."""
    return {
        "category": "career_volatility",
        "score": 0.65,
        "severity": "yellow",
        "evidence": {"job_changes": 5, "avg_tenure": 18},
        "is_flagged": True,
    }


@pytest.fixture
def sample_red_flag_event_data():
    """Sample data for creating a RedFlagEvent."""
    return {
        "flag_type": "high_volatility",
        "severity": "orange",
        "description": "Multiple short-term positions detected",
        "event_metadata": {"positions": 5, "avg_duration": 8},
        "resolved": False,
    }

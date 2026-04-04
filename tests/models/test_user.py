"""Tests for User model."""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class TestUserInstantiation:
    """Test User model instantiation."""

    async def test_user_can_be_created_with_minimal_data(self, db_session: AsyncSession):
        """Test that a user can be created with just email."""
        user = User(email="test@example.com")
        db_session.add(user)
        await db_session.commit()

        assert user.id is not None
        assert isinstance(user.id, uuid.UUID)
        assert user.email == "test@example.com"
        assert user.is_active is True
        assert user.is_superuser is False
        assert user.hashed_password is None

    async def test_user_can_be_created_with_full_data(self, db_session: AsyncSession, sample_user_data):
        """Test that a user can be created with all fields."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        assert user.id is not None
        assert user.email == sample_user_data["email"]
        assert user.hashed_password == sample_user_data["hashed_password"]
        assert user.is_active == sample_user_data["is_active"]
        assert user.is_superuser == sample_user_data["is_superuser"]

    async def test_user_has_timestamps(self, db_session: AsyncSession):
        """Test that user has created_at and updated_at timestamps."""
        user = User(email="test@example.com")
        db_session.add(user)
        await db_session.commit()

        assert user.created_at is not None
        assert user.updated_at is not None
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)


class TestUserConstraints:
    """Test User model constraints."""

    async def test_email_is_required(self, db_session: AsyncSession):
        """Test that email cannot be null."""
        user = User(email=None)
        db_session.add(user)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    async def test_email_must_be_unique(self, db_session: AsyncSession):
        """Test that email must be unique."""
        user1 = User(email="duplicate@example.com")
        db_session.add(user1)
        await db_session.commit()

        user2 = User(email="duplicate@example.com")
        db_session.add(user2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    async def test_is_active_defaults_to_true(self, db_session: AsyncSession):
        """Test that is_active defaults to True."""
        user = User(email="test@example.com")
        db_session.add(user)
        await db_session.commit()

        assert user.is_active is True

    async def test_is_superuser_defaults_to_false(self, db_session: AsyncSession):
        """Test that is_superuser defaults to False."""
        user = User(email="test@example.com")
        db_session.add(user)
        await db_session.commit()

        assert user.is_superuser is False

    async def test_hashed_password_can_be_null(self, db_session: AsyncSession):
        """Test that hashed_password can be null."""
        user = User(email="test@example.com", hashed_password=None)
        db_session.add(user)
        await db_session.commit()

        assert user.hashed_password is None


class TestUserRelationships:
    """Test User model relationships."""

    async def test_user_has_career_profiles_relationship(self, db_session: AsyncSession):
        """Test that user has career_profiles relationship."""
        user = User(email="test@example.com")
        db_session.add(user)
        await db_session.commit()

        # Relationship should exist and be empty list
        assert hasattr(user, "career_profiles")
        assert user.career_profiles == []

    async def test_user_has_job_entries_relationship(self, db_session: AsyncSession):
        """Test that user has job_entries relationship."""
        user = User(email="test@example.com")
        db_session.add(user)
        await db_session.commit()

        assert hasattr(user, "job_entries")
        assert user.job_entries == []

    async def test_user_has_career_analytics_relationship(self, db_session: AsyncSession):
        """Test that user has career_analytics relationship."""
        user = User(email="test@example.com")
        db_session.add(user)
        await db_session.commit()

        assert hasattr(user, "career_analytics")

    async def test_user_has_career_turning_points_relationship(self, db_session: AsyncSession):
        """Test that user has career_turning_points relationship."""
        user = User(email="test@example.com")
        db_session.add(user)
        await db_session.commit()

        assert hasattr(user, "career_turning_points")
        assert user.career_turning_points == []


class TestUserRepresentation:
    """Test User model string representation."""

    async def test_user_repr(self, db_session: AsyncSession):
        """Test user __repr__ method."""
        user = User(email="test@example.com")
        db_session.add(user)
        await db_session.commit()

        repr_str = repr(user)
        assert "User" in repr_str
        assert str(user.id) in repr_str
        assert user.email in repr_str

    async def test_user_str(self, db_session: AsyncSession):
        """Test user string conversion."""
        user = User(email="test@example.com")
        db_session.add(user)
        await db_session.commit()

        str_repr = str(user)
        assert "User" in str_repr

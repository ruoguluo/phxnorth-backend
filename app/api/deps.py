"""API dependencies for FastAPI."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationException, AuthorizationException
from app.core.security import verify_token
from app.database import get_db as get_db_session
from app.models.user import User

if TYPE_CHECKING:
    from app.kafka.producer import KafkaProducerService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_db() -> AsyncSession:
    """Dependency for FastAPI to get database session.

    This is a re-export of get_db from database module for cleaner imports.
    """
    async for session in get_db_session():
        yield session


def get_kafka_producer(request: Request) -> KafkaProducerService | None:
    """Return the Kafka producer from application state, or None if unavailable.

    This allows endpoints to optionally publish to Kafka while falling back
    to synchronous processing when Kafka is not configured or reachable.
    """
    return getattr(request.app.state, "kafka_producer", None)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user from the JWT access token.

    Args:
        token: Bearer token extracted by OAuth2PasswordBearer.
        db: Async database session.

    Returns:
        The authenticated User instance.

    Raises:
        AuthenticationException: If the token is invalid, expired, or user not found.
    """
    try:
        payload = verify_token(token)
    except JWTError:
        raise AuthenticationException(message="Invalid or expired token")

    if payload.get("type") != "access":
        raise AuthenticationException(message="Invalid token type")

    user_id = payload.get("sub")
    if user_id is None:
        raise AuthenticationException(message="Invalid token payload")

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationException(message="User not found")

    if not user.is_active:
        raise AuthenticationException(message="User account is inactive")

    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency that ensures the current user is an admin (superuser).

    Args:
        current_user: The authenticated user from get_current_user.

    Returns:
        The authenticated admin User instance.

    Raises:
        AuthorizationException: If the user is not a superuser.
    """
    if not current_user.is_superuser:
        raise AuthorizationException(message="Admin access required")
    return current_user

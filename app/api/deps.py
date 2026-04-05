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
    from app.cache.dedup import EventDeduplicator
    from app.cache.disc_cache import DISCProfileCache
    from app.cache.redis_client import RedisCacheService
    from app.cache.risk_cache import RiskCache
    from app.kafka.producer import KafkaProducerService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_db() -> AsyncSession:
    """Dependency for FastAPI to get database session.

    This is a re-export of get_db from database module for cleaner imports.
    """
    async for session in get_db_session():
        yield session


def get_redis(request: Request) -> RedisCacheService | None:
    """Return the Redis cache service from application state, or None if unavailable.

    Endpoints should handle the ``None`` case gracefully (e.g. skip caching).
    """
    return getattr(request.app.state, "redis", None)


def get_disc_cache(request: Request) -> DISCProfileCache | None:
    """Return a DISC profile cache instance, or None if Redis is unavailable.

    Endpoints should handle the ``None`` case gracefully (skip caching).
    """
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        return None
    from app.cache.disc_cache import DISCProfileCache

    return DISCProfileCache(redis)


def get_risk_cache(request: Request) -> RiskCache | None:
    """Return a risk cache instance, or None if Redis is unavailable.

    Endpoints should handle the ``None`` case gracefully (skip caching).
    """
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        return None
    from app.cache.risk_cache import RiskCache

    return RiskCache(redis)


def get_deduplicator(request: Request) -> EventDeduplicator | None:
    """Return an event deduplicator instance, or None if Redis is unavailable.

    Endpoints should handle the ``None`` case gracefully (skip dedup).
    """
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        return None
    from app.cache.dedup import EventDeduplicator

    return EventDeduplicator(redis)


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

    Supports two JWT formats:
    1. DISC backend tokens: {"sub": "<uuid>", "type": "access", "role": "..."}
    2. Existing mentorship backend tokens: {"sub": "<email>"}

    This allows users who authenticate via the existing mentorship backend
    to also access DISC endpoints with the same token.

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
    except (JWTError, Exception):
        raise AuthenticationException(message="Invalid or expired token")

    sub = payload.get("sub")
    if sub is None:
        raise AuthenticationException(message="Invalid token payload")

    # Determine if this is a DISC backend token (has "type" field) or
    # an existing mentorship backend token (sub is an email string).
    token_type = payload.get("type")

    if token_type == "access":
        # DISC backend token — sub is a UUID
        try:
            result = await db.execute(select(User).where(User.id == UUID(sub)))
        except (ValueError, AttributeError):
            raise AuthenticationException(message="Invalid token payload")
    else:
        # Existing mentorship backend token — sub is an email
        # Look up user by email, or auto-create a DISC-side user record
        result = await db.execute(select(User).where(User.email == sub))

    user = result.scalar_one_or_none()

    if user is None:
        # Auto-create user record for existing mentorship users on first DISC access
        if token_type != "access" and sub:
            user = User(email=sub, is_active=True)
            db.add(user)
            await db.commit()
            await db.refresh(user)
        else:
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

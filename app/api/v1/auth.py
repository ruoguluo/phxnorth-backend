"""Authentication endpoints: register, login, refresh, logout."""

from fastapi import APIRouter, Depends, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.v1.schemas.auth import (
    MessageResponse,
    RefreshTokenRequest,
    TokenRequest,
    TokenResponse,
    UserRegisterRequest,
    UserResponse,
)
from app.core.exceptions import (
    AuthenticationException,
    ConflictException,
    ValidationException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email and password.",
)
async def register(
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Register a new user.

    Raises:
        ConflictException: If a user with the given email already exists.
    """
    # Check for existing user
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise ConflictException(
            message="A user with this email already exists",
            details={"email": payload.email},
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Login and obtain tokens",
    description="Authenticate with email and password to receive access and refresh tokens.",
)
async def login(
    payload: TokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate a user and return JWT tokens.

    Raises:
        AuthenticationException: If credentials are invalid.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or user.hashed_password is None:
        raise AuthenticationException(message="Invalid email or password")

    if not verify_password(payload.password, user.hashed_password):
        raise AuthenticationException(message="Invalid email or password")

    if not user.is_active:
        raise AuthenticationException(message="User account is inactive")

    token_data = {"sub": str(user.id), "role": "admin" if user.is_superuser else "mentee"}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Exchange a valid refresh token for a new access + refresh token pair.",
)
async def refresh(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Refresh an expired access token using a refresh token.

    Raises:
        AuthenticationException: If the refresh token is invalid or expired.
    """
    try:
        token_payload = verify_token(payload.refresh_token)
    except JWTError:
        raise AuthenticationException(message="Invalid or expired refresh token")

    if token_payload.get("type") != "refresh":
        raise AuthenticationException(message="Token is not a refresh token")

    user_id = token_payload.get("sub")
    if user_id is None:
        raise AuthenticationException(message="Invalid token payload")

    # Verify user still exists and is active
    from uuid import UUID

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise AuthenticationException(message="User not found or inactive")

    token_data = {"sub": str(user.id), "role": "admin" if user.is_superuser else "mentee"}
    new_access_token = create_access_token(data=token_data)
    new_refresh_token = create_refresh_token(data=token_data)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout (invalidate refresh token)",
    description="Invalidate the current refresh token. "
    "Note: With stateless JWTs, this is advisory; "
    "a token blacklist can be added for strict invalidation.",
)
async def logout() -> MessageResponse:
    """Logout the current user.

    With stateless JWTs the access token remains valid until expiry.
    A server-side token blacklist (e.g. in Redis) can be layered on
    for immediate invalidation.
    """
    # TODO: Add refresh token to a Redis-backed blacklist for strict invalidation
    return MessageResponse(message="Successfully logged out")

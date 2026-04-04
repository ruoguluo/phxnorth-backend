"""Pydantic request/response schemas for authentication endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ── Request Schemas ──────────────────────────────────────────────────────────


class UserRegisterRequest(BaseModel):
    """Schema for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class TokenRequest(BaseModel):
    """Schema for token (login) request.

    Also supports OAuth2 password flow via form data — handled separately
    in the endpoint using OAuth2PasswordRequestForm.
    """

    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Schema for refreshing an access token."""

    refresh_token: str


# ── Response Schemas ─────────────────────────────────────────────────────────


class TokenResponse(BaseModel):
    """Schema for token response (login / refresh)."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Schema for returning user data."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    is_active: bool
    is_superuser: bool
    created_at: datetime


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str

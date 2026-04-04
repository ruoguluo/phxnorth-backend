"""Pydantic schemas for CV upload and parsing endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# --- Request Schemas ---


class CVTextRequest(BaseModel):
    """Request body for pasting raw CV text."""

    raw_text: str = Field(
        ...,
        min_length=50,
        max_length=100_000,
        description="Raw CV text content",
    )
    source: str = Field(
        default="paste",
        pattern="^paste$",
        description="Source of the CV text (must be 'paste')",
    )


# --- Response Schemas ---


class CVUploadResponse(BaseModel):
    """Response returned when a CV upload/text job is queued."""

    job_id: UUID
    user_id: UUID
    status: str = Field(default="queued", description="Job status")
    message: str = Field(
        default="CV processing has been queued",
        description="Human-readable status message",
    )


class CVStatusResponse(BaseModel):
    """Response for checking CV parse job status."""

    job_id: UUID
    status: str = Field(description="Job status: queued | processing | completed | failed")
    parsed_at: Optional[datetime] = Field(
        default=None, description="Timestamp when parsing completed"
    )
    entries_found: Optional[int] = Field(
        default=None, description="Number of job entries extracted"
    )
    signals_fired: Optional[int] = Field(
        default=None, description="Number of career signals detected"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if parsing failed"
    )

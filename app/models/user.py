"""User model for authentication and user management."""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class User(BaseModel):
    """User model for authentication and user management."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"

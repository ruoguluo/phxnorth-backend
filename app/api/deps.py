"""API dependencies for FastAPI."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db as get_db_session


async def get_db() -> AsyncSession:
    """Dependency for FastAPI to get database session.
    
    This is a re-export of get_db from database module for cleaner imports.
    """
    async for session in get_db_session():
        yield session

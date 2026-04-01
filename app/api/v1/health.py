"""Health check endpoints for monitoring and Kubernetes probes."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Full health check with database connectivity",
    description="Returns detailed health status including database connectivity check.",
)
async def health_check(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Full health check endpoint with database connectivity test.
    
    Returns:
        dict: Health status with database connectivity information.
    """
    settings = get_settings()
    
    # Check database connectivity
    try:
        result = await db.execute(text("SELECT 1"))
        db_status = "connected" if result.scalar() == 1 else "error"
    except Exception as e:
        db_status = f"error: {type(e).__name__}"
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.version,
        "environment": settings.environment,
        "database": db_status,
    }


@router.get(
    "/ready",
    response_model=dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Kubernetes readiness probe",
    description="Returns 200 when the application is ready to accept traffic.",
)
async def readiness_probe(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Kubernetes readiness probe endpoint.
    
    Checks if the application is ready to accept traffic.
    Verifies database connectivity.
    
    Returns:
        dict: Readiness status.
    
    Raises:
        HTTPException: 503 if database is not accessible.
    """
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar() != 1:
            return {"status": "not ready", "reason": "database check failed"}
    except Exception as e:
        return {"status": "not ready", "reason": f"database error: {type(e).__name__}"}
    
    return {"status": "ready"}


@router.get(
    "/live",
    response_model=dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Kubernetes liveness probe",
    description="Returns 200 if the application is running and alive.",
)
async def liveness_probe() -> dict[str, str]:
    """Kubernetes liveness probe endpoint.
    
    Simple check to verify the application is running.
    Does not check external dependencies.
    
    Returns:
        dict: Liveness status.
    """
    return {"status": "alive"}

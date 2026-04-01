"""API router for v1 endpoints."""

from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()

# Include health check routes
api_router.include_router(health.router, prefix="/health", tags=["health"])

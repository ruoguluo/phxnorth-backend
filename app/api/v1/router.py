"""API router for v1 endpoints."""

from fastapi import APIRouter

from app.api.v1 import auth, cv, events, health

api_router = APIRouter()

# Include health check routes
api_router.include_router(health.router, prefix="/health", tags=["health"])

# Include auth routes
api_router.include_router(auth.router, tags=["auth"])

# Include event ingestion routes
api_router.include_router(events.router, prefix="/events", tags=["events"])

# Include CV upload/parsing routes
api_router.include_router(cv.router, tags=["cv"])

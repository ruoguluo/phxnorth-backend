"""API router for v1 endpoints."""

from fastapi import APIRouter

from app.api.v1 import admin, auth, career, cv, disc, events, health, risk, webhooks

api_router = APIRouter()

# Include health check routes
api_router.include_router(health.router, prefix="/health", tags=["health"])

# Include auth routes
api_router.include_router(auth.router, tags=["auth"])

# Include event ingestion routes
api_router.include_router(events.router, prefix="/events", tags=["events"])

# Include CV upload/parsing routes
api_router.include_router(cv.router, tags=["cv"])

# Include DISC profile query routes
api_router.include_router(disc.router, tags=["disc"])

# Include risk assessment, contradiction, and behavioral shift routes
api_router.include_router(risk.router, tags=["risk"])

# Include career profile and preference index routes
api_router.include_router(career.router, tags=["career"])

# Include webhook registration routes
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

# Include admin-only routes
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

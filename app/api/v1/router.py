"""API router for v1 endpoints."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_db
from app.api.v1 import (
    admin,
    auth,
    career,
    cv,
    disc,
    events,
    health,
    questions,
    risk,
    webhooks,
)
from app.models.user import User

api_router = APIRouter()


@api_router.get("/disc-profile-by-email", tags=["disc"])
async def get_disc_profile_by_email(
    email: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Look up a user by email and return their DISC profile.

    Used by the mentorship frontend to show a mentee's 5D snapshot
    on the mentor's Review & Structure page.
    """
    from fastapi import HTTPException
    from sqlalchemy import select

    from app.api.v1.disc import get_disc_profile, WindowParam
    from app.models.user import User as UserModel

    result = await db.execute(select(UserModel).where(UserModel.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found by email")

    return await get_disc_profile(user.id, WindowParam.DAYS_90, current_user, db, None)


@api_router.get("/users/me", tags=["users"])
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user's DISC backend info.

    This endpoint resolves the JWT token (from either backend) to the
    DISC backend user record, auto-creating one if needed.
    """
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "is_active": current_user.is_active,
    }


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

# Include AI question-structuring routes (FR-03)
api_router.include_router(questions.router, tags=["questions"])

# Include webhook registration routes
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

# Include admin-only routes
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

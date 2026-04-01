"""Main FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.exceptions import (
    AuthenticationException,
    AuthorizationException,
    ConflictException,
    NotFoundException,
    PhxNorthException,
    ValidationException,
    authentication_exception_handler,
    authorization_exception_handler,
    conflict_exception_handler,
    not_found_exception_handler,
    phxnorth_exception_handler,
    validation_exception_handler,
)
from app.logging_config import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup/shutdown events."""
    # Startup
    settings = get_settings()
    setup_logging()
    
    # Initialize database connections, etc.
    # TODO: Add database initialization when Task 6 is complete
    
    yield
    
    # Shutdown
    # TODO: Cleanup resources when needed


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="Behavioral intelligence infrastructure with DISC scoring",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )
    
    # Add CORS middleware (development only)
    if settings.is_development:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # Register exception handlers
    app.add_exception_handler(PhxNorthException, phxnorth_exception_handler)
    app.add_exception_handler(NotFoundException, not_found_exception_handler)
    app.add_exception_handler(ValidationException, validation_exception_handler)
    app.add_exception_handler(AuthenticationException, authentication_exception_handler)
    app.add_exception_handler(AuthorizationException, authorization_exception_handler)
    app.add_exception_handler(ConflictException, conflict_exception_handler)
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint returning basic API information."""
        return {
            "name": settings.app_name,
            "version": settings.version,
            "environment": settings.environment,
            "docs": "/docs" if settings.is_development else None,
        }
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}
    
    # Include API router
    from app.api.v1.router import api_router
    app.include_router(api_router, prefix=settings.api_prefix)
    
    return app


# Create the application instance
app = create_application()

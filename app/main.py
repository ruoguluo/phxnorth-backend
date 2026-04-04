"""Main FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.cache.redis_client import RedisCacheService
from app.config import get_settings
from app.kafka.producer import KafkaProducerService
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

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup/shutdown events."""
    # Startup
    settings = get_settings()
    setup_logging()
    
    # Initialize database connections, etc.
    # TODO: Add database initialization when Task 6 is complete
    
    # Start Redis cache (optional — gracefully degrade if unavailable)
    redis_cache: RedisCacheService | None = None
    try:
        redis_cache = RedisCacheService()
        await redis_cache.connect()
        app.state.redis = redis_cache
        logger.info("redis_cache_attached_to_app")
    except Exception:
        logger.warning(
            "redis_cache_unavailable",
            msg="Redis failed to connect; cache operations will be unavailable.",
        )
        app.state.redis = None
    
    # Start Kafka producer (optional — gracefully degrade if unavailable)
    kafka_producer: KafkaProducerService | None = None
    try:
        kafka_producer = KafkaProducerService()
        await kafka_producer.start()
        app.state.kafka_producer = kafka_producer
        logger.info("kafka_producer_attached_to_app")
    except Exception:
        logger.warning(
            "kafka_producer_unavailable",
            msg="Kafka producer failed to start; endpoints will use synchronous fallback.",
        )
        app.state.kafka_producer = None
    
    yield
    
    # Shutdown
    if kafka_producer is not None:
        await kafka_producer.stop()
    if redis_cache is not None:
        await redis_cache.disconnect()


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

"""Structured logging configuration using structlog."""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor

from app.config import get_settings


settings = get_settings()


def setup_logging() -> None:
    """Set up structured logging with structlog.
    
    Sets up structlog with appropriate processors for both
    JSON logs (production) and pretty console logs (development).
    """
    configure_logging()


def configure_logging() -> None:
    """Configure structured logging with structlog.
    
    Sets up structlog with appropriate processors for both
    JSON logs (production) and pretty console logs (development).
    """
    shared_processors: list[Processor] = [
        # Add log level to event dict
        structlog.stdlib.add_log_level,
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Add caller info
        structlog.processors.CallsiteParameterAdder(
            [
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
        # Add extra attributes from context vars
        structlog.contextvars.merge_contextvars,
    ]

    if settings.ENVIRONMENT == "development":
        # Pretty console output for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # JSON output for production
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LOG_LEVEL.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper()),
    )

    # Replace standard library logging handlers with structlog
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True)
            if settings.ENVIRONMENT == "development"
            else structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    )

    # Update root logger
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.
    
    Args:
        name: Optional logger name for identification
        
    Returns:
        A configured structlog logger instance
    """
    return structlog.get_logger(name)

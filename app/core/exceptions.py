"""Custom exceptions for the PhxNorth application."""

from typing import Any, Dict, Optional


class PhxNorthException(Exception):
    """Base exception for all PhxNorth application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        return {
            "error": {
                "message": self.message,
                "code": self.status_code,
                "details": self.details,
            }
        }


class NotFoundException(PhxNorthException):
    """Exception raised when a requested resource is not found."""

    def __init__(
        self,
        resource: str = "Resource",
        identifier: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with identifier '{identifier}' not found"

        super().__init__(
            message=message,
            status_code=404,
            details=details,
        )
        self.resource = resource
        self.identifier = identifier


class ValidationException(PhxNorthException):
    """Exception raised when request validation fails."""

    def __init__(
        self,
        message: str = "Validation error",
        field_errors: Optional[Dict[str, str]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        merged_details = details or {}
        if field_errors:
            merged_details["field_errors"] = field_errors

        super().__init__(
            message=message,
            status_code=422,
            details=merged_details,
        )
        self.field_errors = field_errors or {}


class AuthenticationException(PhxNorthException):
    """Exception raised when authentication fails."""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=401,
            details=details,
        )


class AuthorizationException(PhxNorthException):
    """Exception raised when authorization fails."""

    def __init__(
        self,
        message: str = "Access denied",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=403,
            details=details,
        )


class ConflictException(PhxNorthException):
    """Exception raised when a conflict occurs (e.g., duplicate resource)."""

    def __init__(
        self,
        message: str = "Resource conflict",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=409,
            details=details,
        )


# FastAPI exception handlers
from fastapi import Request
from fastapi.responses import JSONResponse


async def phxnorth_exception_handler(
    request: Request, exc: PhxNorthException
) -> JSONResponse:
    """Handle all PhxNorthException subclasses."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


async def not_found_exception_handler(
    request: Request, exc: NotFoundException
) -> JSONResponse:
    """Handle NotFoundException."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


async def validation_exception_handler(
    request: Request, exc: ValidationException
) -> JSONResponse:
    """Handle ValidationException."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


async def authentication_exception_handler(
    request: Request, exc: AuthenticationException
) -> JSONResponse:
    """Handle AuthenticationException."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
        headers={"WWW-Authenticate": "Bearer"},
    )


async def authorization_exception_handler(
    request: Request, exc: AuthorizationException
) -> JSONResponse:
    """Handle AuthorizationException."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


async def conflict_exception_handler(
    request: Request, exc: ConflictException
) -> JSONResponse:
    """Handle ConflictException."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )

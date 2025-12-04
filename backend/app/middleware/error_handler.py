"""Global error handling."""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings

logger = logging.getLogger(__name__)


def _get_cors_headers(request: Request) -> dict[str, str]:
    """Build CORS headers for error responses based on request origin."""
    origin = request.headers.get("origin")
    if not origin:
        return {}

    settings = get_settings()
    allowed_origins = settings.cors_origins_list

    # Check if origin is allowed (support wildcard)
    if "*" in allowed_origins or origin in allowed_origins:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        }

    return {}


def _cors_json_response(
    request: Request,
    status_code: int,
    content: dict[str, Any],
) -> JSONResponse:
    """Create JSONResponse with CORS headers for error responses."""
    headers = _get_cors_headers(request)
    return JSONResponse(status_code=status_code, content=content, headers=headers)


class AppError(Exception):
    """Base application error."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


def create_error_response(
    code: str,
    message: str,
    details: dict = None,
) -> dict:
    """Create standardized error response."""
    error = {
        "code": code,
        "message": message,
    }
    if details:
        error["details"] = details

    return {"error": error}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle custom application errors."""
    logger.error(f"AppException: {exc.code} - {exc.message}")
    return _cors_json_response(
        request,
        exc.status_code,
        create_error_response(exc.code, exc.message, exc.details),
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Handle HTTP exceptions."""
    # Check if detail is already in our format
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return _cors_json_response(request, exc.status_code, exc.detail)

    # Map status codes to error codes
    code_map = {
        400: "VALIDATION_ERROR",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_ERROR",
        502: "LLM_ERROR",
        503: "SERVICE_UNAVAILABLE",
        504: "LLM_TIMEOUT",
    }

    code = code_map.get(exc.status_code, "ERROR")
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

    return _cors_json_response(
        request,
        exc.status_code,
        create_error_response(code, message),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle request validation errors."""
    errors = exc.errors()

    # Format validation errors
    details = {}
    for error in errors:
        loc = ".".join(str(x) for x in error["loc"])
        details[loc] = error["msg"]

    logger.warning(f"Validation error: {details}")

    return _cors_json_response(
        request,
        status.HTTP_400_BAD_REQUEST,
        create_error_response(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details=details,
        ),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.exception(f"Unexpected error: {exc}")

    return _cors_json_response(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        create_error_response(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred",
        ),
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

"""Common Pydantic schemas for API responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Error detail structure."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human readable message")
    details: dict[str, Any] | None = Field(None, description="Additional details")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail


class HealthResponse(BaseModel):
    """Basic health check response."""

    status: str = Field(..., description="Health status: ok, degraded, error")


class ServiceHealth(BaseModel):
    """Individual service health."""

    status: str
    latency_ms: float | None = None
    error: str | None = None


class DetailedHealthResponse(BaseModel):
    """Detailed health check response with service statuses."""

    status: str
    services: dict[str, ServiceHealth]
    queue_length: int | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseModel):
    """Base for paginated responses."""

    total: int
    limit: int
    offset: int

"""Rate limiting middleware."""

import logging
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings
from app.redis.client import RedisClient
from app.redis.keys import RedisKeys
from app.redis.rate_limiter import SlidingWindowRateLimiter

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using sliding window algorithm.

    Applies rate limits based on X-Session-ID header or client IP.
    Adds rate limit headers to all responses.
    """

    # Paths to exclude from rate limiting
    EXCLUDED_PATHS = {"/api/v1/health", "/api/v1/health/ready", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Skip excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Get Redis client from app state
        redis: RedisClient = request.app.state.redis
        settings = get_settings()

        # Create rate limiter
        limiter = SlidingWindowRateLimiter(
            redis=redis.client,
            max_requests=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )

        # Get identifier (session ID or IP)
        session_id = request.headers.get("X-Session-ID")
        client_ip = request.client.host if request.client else "unknown"
        identifier = session_id or client_ip

        # Check rate limit
        key = RedisKeys.rate_limit(identifier)
        result = await limiter.check(key)

        # Add rate limit headers
        headers = {
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": str(result.remaining),
            "X-RateLimit-Reset": str(int(result.reset_at)),
        }

        if not result.allowed:
            logger.warning(f"Rate limit exceeded for {identifier}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please try again later.",
                        "details": {
                            "retry_after": int(result.retry_after),
                        },
                    }
                },
                headers={
                    **headers,
                    "Retry-After": str(int(result.retry_after)),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = value

        return response

# Last Updated: 2025-12-03

## Purpose
FastAPI middleware for request tracing, error handling, and rate limiting.

## Key Files
- `request_id.py` - Adds unique X-Request-ID to all requests/responses for tracing
- `error_handler.py` - Global exception handlers (AppError, HTTP, validation), standardized error responses
- `rate_limiter.py` - Token bucket rate limiting per IP using Redis

## Dependencies/Relations
Used by `app/main.py`. Depends on `redis/` for rate limiting.

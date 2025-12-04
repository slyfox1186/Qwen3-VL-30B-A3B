# Last Updated: 2025-12-03

## Purpose
Redis client with connection pooling, key patterns, rate limiting, and queue primitives.

## Key Files
- `client.py` - Singleton async Redis client with connection pooling, health checks, pipeline context manager
- `keys.py` - RedisKeys helper for consistent key patterns (session:*, history:*)
- `rate_limiter.py` - Token bucket rate limiter implementation
- `queue.py` - Redis Streams queue primitives for task processing

## Dependencies/Relations
Used by `services/`, `middleware/rate_limiter`. Initialized in `main.py` lifespan.

"""Sliding window rate limiter using Redis sorted sets with Lua script."""

import time
from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass
class RateLimitResult:
    """Result of rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_at: float
    retry_after: float = 0.0


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter using Redis sorted sets.

    Uses a Lua script for atomic operations to prevent race conditions.
    """

    # Lua script for atomic rate limiting
    LUA_SCRIPT = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    local window_start = now - window

    -- Remove expired entries
    redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

    -- Count current requests
    local current = redis.call('ZCARD', key)

    if current < limit then
        -- Add new request with unique member
        redis.call('ZADD', key, now, now .. '-' .. math.random(1000000))
        redis.call('EXPIRE', key, window + 1)
        return {1, limit - current - 1, 0}
    else
        -- Get oldest entry to calculate retry time
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        local retry_after = 0
        if oldest and oldest[2] then
            retry_after = oldest[2] + window - now
        end
        return {0, 0, retry_after}
    end
    """

    def __init__(
        self,
        redis: Redis,
        max_requests: int,
        window_seconds: int,
    ) -> None:
        self._redis = redis
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._script = None

    async def _get_script(self):
        """Get or register Lua script."""
        if self._script is None:
            self._script = self._redis.register_script(self.LUA_SCRIPT)
        return self._script

    async def check(self, key: str) -> RateLimitResult:
        """
        Check if request is allowed under rate limit.

        Args:
            key: Rate limit key (e.g., session ID or IP)

        Returns:
            RateLimitResult with allowed status and metadata
        """
        script = await self._get_script()
        now = time.time()

        result = await script(
            keys=[key],
            args=[now, self._window_seconds, self._max_requests],
        )

        allowed = bool(result[0])
        remaining = int(result[1])
        retry_after = float(result[2])
        reset_at = now + self._window_seconds

        return RateLimitResult(
            allowed=allowed,
            limit=self._max_requests,
            remaining=remaining,
            reset_at=reset_at,
            retry_after=retry_after if not allowed else 0.0,
        )

    async def get_usage(self, key: str) -> tuple[int, int]:
        """
        Get current usage for a key.

        Returns:
            Tuple of (current_count, limit)
        """
        now = time.time()
        window_start = now - self._window_seconds

        # Remove expired and count
        await self._redis.zremrangebyscore(key, "-inf", window_start)
        current = await self._redis.zcard(key)

        return current, self._max_requests

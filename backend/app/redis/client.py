"""Async Redis client with connection pooling."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional

import redis.asyncio as redis
from redis.asyncio import ConnectionPool, Redis

from app.config import get_settings

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Production Redis client with connection pooling.

    Features:
    - Lazy initialization
    - Connection pooling
    - Automatic reconnection
    - Health checks
    """

    _instance: Optional["RedisClient"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        self._pool: ConnectionPool | None = None
        self._client: Redis | None = None
        self._initialized = False
        self._settings = get_settings()

    @classmethod
    async def get_instance(cls) -> "RedisClient":
        """Thread-safe singleton access."""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance.connect()
        return cls._instance

    async def connect(self) -> None:
        """Initialize connection pool."""
        if self._initialized:
            return

        try:
            self._pool = ConnectionPool.from_url(
                self._settings.redis_url,
                max_connections=self._settings.redis_max_connections,
                decode_responses=True,
                socket_timeout=self._settings.redis_socket_timeout,
                socket_connect_timeout=self._settings.redis_socket_timeout,
                retry_on_timeout=True,
            )
            self._client = Redis(connection_pool=self._pool)

            # Verify connection
            await self._client.ping()
            self._initialized = True
            logger.info("Redis connection established")

        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.disconnect()
            self._initialized = False
            logger.info("Redis connection closed")

    @property
    def client(self) -> Redis:
        """Get Redis client instance."""
        if not self._client or not self._initialized:
            raise RuntimeError("Redis client not initialized. Call connect() first.")
        return self._client

    @asynccontextmanager
    async def pipeline(self, transaction: bool = True) -> AsyncGenerator:
        """Context manager for Redis pipelines."""
        pipe = self.client.pipeline(transaction=transaction)
        try:
            yield pipe
            await pipe.execute()
        except Exception:
            raise

    async def health_check(self) -> bool:
        """Check if Redis is healthy."""
        try:
            await self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Global instance accessor
async def get_redis() -> RedisClient:
    """Get Redis client instance."""
    return await RedisClient.get_instance()

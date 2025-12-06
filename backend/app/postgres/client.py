"""Async PostgreSQL client with connection pooling for long-term memory."""

import asyncio
import logging
from typing import Optional

import asyncpg
from asyncpg import Pool
from pgvector.asyncpg import register_vector

from app.config import get_settings

logger = logging.getLogger(__name__)


class PostgresClient:
    """
    Production PostgreSQL client with connection pooling.

    Features:
    - Lazy initialization
    - Connection pooling via asyncpg
    - pgvector type registration
    - Health checks
    - Singleton pattern
    """

    _instance: Optional["PostgresClient"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        self._pool: Pool | None = None
        self._initialized = False
        self._settings = get_settings()

    @classmethod
    async def get_instance(cls) -> "PostgresClient":
        """Thread-safe singleton access."""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance.connect()
        return cls._instance

    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """Initialize each connection with pgvector support."""
        await register_vector(conn)

    async def connect(self) -> None:
        """Initialize connection pool."""
        if self._initialized:
            return

        try:
            self._pool = await asyncpg.create_pool(
                host=self._settings.postgres_host,
                port=self._settings.postgres_port,
                user=self._settings.postgres_user,
                password=self._settings.postgres_password,
                database=self._settings.postgres_database,
                min_size=self._settings.postgres_pool_min,
                max_size=self._settings.postgres_pool_max,
                command_timeout=60,
                max_queries=50000,
                max_inactive_connection_lifetime=300.0,
                init=self._init_connection,
            )

            # Verify connection
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")

            self._initialized = True
            logger.info("PostgreSQL connection pool established")

        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._initialized = False
            logger.info("PostgreSQL connection pool closed")

    @property
    def pool(self) -> Pool:
        """Get the connection pool."""
        if not self._pool or not self._initialized:
            raise RuntimeError("PostgreSQL not initialized. Call connect() first.")
        return self._pool

    async def health_check(self) -> bool:
        """Check if PostgreSQL is healthy."""
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            return False


async def get_postgres() -> PostgresClient:
    """Get PostgreSQL client instance."""
    return await PostgresClient.get_instance()

"""Session lifecycle management."""

import logging

from app.models.domain.session import Session
from app.redis.client import RedisClient
from app.redis.keys import RedisKeys

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages session lifecycle in Redis.

    Features:
    - Create/read/delete sessions
    - TTL management with refresh on access
    - Session metadata
    """

    def __init__(self, redis: RedisClient, ttl_seconds: int):
        self._redis = redis
        self._ttl = ttl_seconds

    async def create_session(
        self,
        user_id: str | None = None,
        metadata: dict | None = None,
    ) -> Session:
        """
        Create a new chat session.

        Args:
            user_id: Optional user identifier
            metadata: Optional custom metadata

        Returns:
            Created Session object
        """
        session = Session(
            user_id=user_id,
            metadata=metadata,
        )

        key = RedisKeys.session(session.id)
        await self._redis.client.setex(
            key,
            self._ttl,
            session.to_json(),
        )

        logger.info(f"Created session {session.id}")
        return session

    async def get_session(self, session_id: str) -> Session | None:
        """
        Retrieve session by ID.

        Refreshes TTL on access.

        Args:
            session_id: Session identifier

        Returns:
            Session object or None if not found
        """
        key = RedisKeys.session(session_id)
        data = await self._redis.client.get(key)

        if not data:
            return None

        # Refresh TTL on access
        await self._redis.client.expire(key, self._ttl)

        session = Session.from_json(data)
        return session

    async def update_session(self, session: Session) -> None:
        """
        Update session data.

        Args:
            session: Session object to update
        """
        session.touch()
        key = RedisKeys.session(session.id)
        await self._redis.client.setex(
            key,
            self._ttl,
            session.to_json(),
        )

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete session and its history.

        Args:
            session_id: Session identifier

        Returns:
            True if session was deleted
        """
        session_key = RedisKeys.session(session_id)
        history_key = RedisKeys.session_history(session_id)

        deleted = await self._redis.client.delete(session_key, history_key)

        if deleted > 0:
            logger.info(f"Deleted session {session_id}")
            return True

        return False

    async def session_exists(self, session_id: str) -> bool:
        """Check if session exists."""
        key = RedisKeys.session(session_id)
        return await self._redis.client.exists(key) > 0

    async def increment_message_count(
        self,
        session_id: str,
        count: int = 1,
    ) -> None:
        """
        Increment session message count.

        Args:
            session_id: Session identifier
            count: Number to increment by
        """
        session = await self.get_session(session_id)
        if session:
            session.increment_messages(count)
            await self.update_session(session)

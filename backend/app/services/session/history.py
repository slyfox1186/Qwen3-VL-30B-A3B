"""Chat history management."""

import logging

from app.models.domain.message import Message
from app.redis.client import RedisClient
from app.redis.keys import RedisKeys

logger = logging.getLogger(__name__)


class ChatHistoryService:
    """
    Manages chat history in Redis.

    Features:
    - Append messages with automatic trimming
    - Retrieve history with pagination
    - Clear history
    """

    def __init__(self, redis: RedisClient, max_messages: int):
        self._redis = redis
        self._max_messages = max_messages

    async def append_message(
        self,
        session_id: str,
        message: Message,
        ttl_seconds: int,
    ) -> None:
        """
        Append message to history with automatic trimming.

        Args:
            session_id: Session identifier
            message: Message to append
            ttl_seconds: TTL for the history key
        """
        message.session_id = session_id
        key = RedisKeys.session_history(session_id)

        async with self._redis.pipeline() as pipe:
            # Append to list
            await pipe.rpush(key, message.to_json())
            # Trim to max messages (keep last N)
            await pipe.ltrim(key, -self._max_messages, -1)
            # Refresh TTL
            await pipe.expire(key, ttl_seconds)

        logger.debug(f"Appended message to session {session_id}")

    async def get_history(
        self,
        session_id: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Message]:
        """
        Retrieve chat history.

        Args:
            session_id: Session identifier
            limit: Maximum messages to return (None for all)
            offset: Number of messages to skip from start

        Returns:
            List of Message objects
        """
        key = RedisKeys.session_history(session_id)

        if limit:
            # Calculate Redis list indices
            start = offset
            end = offset + limit - 1
            data = await self._redis.client.lrange(key, start, end)
        else:
            data = await self._redis.client.lrange(key, 0, -1)

        messages = [Message.from_json(item) for item in data]
        return messages

    async def get_history_count(self, session_id: str) -> int:
        """
        Get total message count in history.

        Args:
            session_id: Session identifier

        Returns:
            Number of messages
        """
        key = RedisKeys.session_history(session_id)
        return await self._redis.client.llen(key)

    async def get_recent_messages(
        self,
        session_id: str,
        count: int,
    ) -> list[Message]:
        """
        Get most recent messages.

        Args:
            session_id: Session identifier
            count: Number of recent messages to get

        Returns:
            List of Message objects (oldest first)
        """
        key = RedisKeys.session_history(session_id)
        data = await self._redis.client.lrange(key, -count, -1)
        return [Message.from_json(item) for item in data]

    async def clear_history(self, session_id: str) -> None:
        """
        Clear chat history for session.

        Args:
            session_id: Session identifier
        """
        key = RedisKeys.session_history(session_id)
        await self._redis.client.delete(key)
        logger.info(f"Cleared history for session {session_id}")

    async def get_context_messages(
        self,
        session_id: str,
        max_messages: int | None = None,
    ) -> list[Message]:
        """
        Get messages formatted for LLM context.

        Args:
            session_id: Session identifier
            max_messages: Maximum messages for context

        Returns:
            List of Message objects for LLM input
        """
        count = max_messages or self._max_messages
        return await self.get_recent_messages(session_id, count)

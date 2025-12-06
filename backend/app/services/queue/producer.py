"""Queue producer for LLM requests."""

from typing import Any

from app.redis.client import RedisClient
from app.redis.queue import QueueProducer as BaseQueueProducer


class LLMQueueProducer:
    """
    Produces LLM requests to the queue.

    Wrapper around the base queue producer with
    convenience methods for LLM-specific operations.
    """

    def __init__(self, redis: RedisClient):
        self._producer = BaseQueueProducer(redis.client)

    async def enqueue_chat_request(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.6,
        priority: int = 5,
        timeout_ms: int = 60000,
    ) -> str:
        """
        Enqueue a chat completion request.

        Args:
            session_id: Session identifier
            messages: Chat messages for LLM
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            priority: Queue priority (0-9, lower is higher)
            timeout_ms: Request timeout

        Returns:
            Request ID for tracking
        """
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        return await self._producer.enqueue(
            session_id=session_id,
            messages=[payload],  # Wrap in list for queue format
            priority=priority,
            timeout_ms=timeout_ms,
        )

    async def get_queue_status(self) -> dict[str, Any]:
        """Get queue status information."""
        return await self._producer.get_queue_info()

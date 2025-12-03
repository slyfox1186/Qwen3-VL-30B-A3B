"""Redis Streams-based request queue for LLM inference."""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from redis.asyncio import Redis

from app.redis.keys import RedisKeys

logger = logging.getLogger(__name__)


@dataclass
class QueuedRequest:
    """Queued LLM request."""

    request_id: str
    session_id: str
    messages: list[dict[str, Any]]
    priority: int = 5
    created_at: float = field(default_factory=time.time)
    timeout_ms: int = 60000
    entry_id: str | None = None

    def to_stream_entry(self) -> dict[str, str]:
        """Convert to Redis Stream entry format."""
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "messages": json.dumps(self.messages),
            "priority": str(self.priority),
            "created_at": str(int(self.created_at * 1000)),
            "timeout_ms": str(self.timeout_ms),
        }

    @classmethod
    def from_stream_entry(cls, entry_id: str, data: dict[str, str]) -> "QueuedRequest":
        """Create from Redis Stream entry."""
        return cls(
            request_id=data["request_id"],
            session_id=data["session_id"],
            messages=json.loads(data["messages"]),
            priority=int(data["priority"]),
            created_at=float(data["created_at"]) / 1000,
            timeout_ms=int(data["timeout_ms"]),
            entry_id=entry_id,
        )


class QueueProducer:
    """Produces LLM requests to Redis Streams queue."""

    def __init__(self, redis: Redis, stream_name: str | None = None) -> None:
        self._redis = redis
        self._stream = stream_name or RedisKeys.request_queue()

    async def enqueue(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
        priority: int = 5,
        timeout_ms: int = 60000,
    ) -> str:
        """
        Add request to queue.

        Args:
            session_id: Session identifier
            messages: Chat messages for LLM
            priority: Priority level (0-9, lower is higher)
            timeout_ms: Request timeout in milliseconds

        Returns:
            request_id: Unique request identifier
        """
        request_id = str(uuid.uuid4())

        request = QueuedRequest(
            request_id=request_id,
            session_id=session_id,
            messages=messages,
            priority=priority,
            timeout_ms=timeout_ms,
        )

        entry_id = await self._redis.xadd(
            self._stream,
            request.to_stream_entry(),
            maxlen=10000,  # Prevent unbounded growth
        )

        logger.debug(f"Enqueued request {request_id} with entry {entry_id}")
        return request_id

    async def get_queue_length(self) -> int:
        """Get current queue length."""
        return await self._redis.xlen(self._stream)

    async def get_queue_info(self) -> dict[str, Any]:
        """Get queue statistics."""
        length = await self._redis.xlen(self._stream)
        info = await self._redis.xinfo_stream(self._stream)
        return {
            "length": length,
            "first_entry": info.get("first-entry"),
            "last_entry": info.get("last-entry"),
            "groups": info.get("groups", 0),
        }


class QueueConsumer:
    """Consumes and processes LLM requests from Redis Streams."""

    def __init__(
        self,
        redis: Redis,
        stream_name: str | None = None,
        consumer_group: str = "llm_workers",
        consumer_name: str | None = None,
    ) -> None:
        self._redis = redis
        self._stream = stream_name or RedisKeys.request_queue()
        self._group = consumer_group
        self._consumer = consumer_name or f"worker-{uuid.uuid4().hex[:8]}"
        self._running = False

    async def setup(self) -> None:
        """Create consumer group if not exists."""
        try:
            await self._redis.xgroup_create(
                self._stream,
                self._group,
                id="0",
                mkstream=True,
            )
            logger.info(f"Created consumer group {self._group}")
        except Exception as e:
            if "BUSYGROUP" in str(e):
                logger.debug(f"Consumer group {self._group} already exists")
            else:
                raise

    async def dequeue(self, block_ms: int = 5000) -> QueuedRequest | None:
        """
        Dequeue next request.

        Args:
            block_ms: How long to block waiting for messages

        Returns:
            QueuedRequest or None if timeout
        """
        messages = await self._redis.xreadgroup(
            groupname=self._group,
            consumername=self._consumer,
            streams={self._stream: ">"},
            count=1,
            block=block_ms,
        )

        if not messages:
            return None

        for stream_name, stream_messages in messages:
            for msg_id, msg_data in stream_messages:
                return QueuedRequest.from_stream_entry(msg_id, msg_data)

        return None

    async def acknowledge(self, entry_id: str) -> None:
        """Acknowledge processed message."""
        await self._redis.xack(self._stream, self._group, entry_id)
        logger.debug(f"Acknowledged entry {entry_id}")

    async def reject(self, entry_id: str) -> None:
        """Reject message (will be reprocessed)."""
        # Message stays in pending, will be claimed by another consumer
        logger.warning(f"Rejected entry {entry_id}")

    async def run(
        self,
        handler: Callable[[QueuedRequest], Any],
        batch_size: int = 1,
    ) -> None:
        """
        Main consumer loop.

        Args:
            handler: Async function to process each request
            batch_size: Number of messages to fetch at once
        """
        await self.setup()
        self._running = True

        logger.info(f"Consumer {self._consumer} starting...")

        while self._running:
            try:
                request = await self.dequeue()

                if request:
                    try:
                        await handler(request)
                        if request.entry_id:
                            await self.acknowledge(request.entry_id)
                    except Exception as e:
                        logger.error(f"Error processing request {request.request_id}: {e}")
                        if request.entry_id:
                            await self.reject(request.entry_id)

            except asyncio.CancelledError:
                logger.info("Consumer cancelled")
                break
            except Exception as e:
                logger.error(f"Consumer error: {e}")
                await asyncio.sleep(1)

        logger.info(f"Consumer {self._consumer} stopped")

    def stop(self) -> None:
        """Stop the consumer loop."""
        self._running = False

    async def check_pending(self, max_idle_ms: int = 60000) -> list[str]:
        """
        Check for timed-out pending messages.

        Args:
            max_idle_ms: Maximum idle time before considering message stuck

        Returns:
            List of entry IDs that are stuck
        """
        try:
            pending = await self._redis.xpending_range(
                self._stream,
                self._group,
                min="-",
                max="+",
                count=100,
            )

            stuck = []
            for msg in pending:
                if msg.get("time_since_delivered", 0) > max_idle_ms:
                    stuck.append(msg["message_id"])

            return stuck
        except Exception as e:
            logger.error(f"Error checking pending: {e}")
            return []

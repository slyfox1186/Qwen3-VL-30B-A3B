"""Queue consumer for processing LLM requests."""

import logging

from app.redis.client import RedisClient
from app.redis.queue import QueueConsumer as BaseQueueConsumer
from app.redis.queue import QueuedRequest
from app.services.llm.client import VLLMClient

logger = logging.getLogger(__name__)


class LLMQueueConsumer:
    """
    Consumes and processes LLM requests from the queue.

    Handles background processing of queued LLM requests.
    """

    def __init__(
        self,
        redis: RedisClient,
        llm_client: VLLMClient,
        consumer_group: str = "llm_workers",
        consumer_name: str | None = None,
    ):
        self._redis = redis
        self._llm_client = llm_client
        self._consumer = BaseQueueConsumer(
            redis=redis.client,
            consumer_group=consumer_group,
            consumer_name=consumer_name,
        )

    async def start(self) -> None:
        """Start processing queued requests."""
        await self._consumer.run(self._process_request)

    def stop(self) -> None:
        """Stop processing."""
        self._consumer.stop()

    async def _process_request(self, request: QueuedRequest) -> None:
        """
        Process a single queued request.

        Args:
            request: The queued request to process
        """
        logger.info(f"Processing request {request.request_id}")

        try:
            # Extract parameters from the queued message
            if request.messages and len(request.messages) > 0:
                params = request.messages[0]
                messages = params.get("messages", [])
                max_tokens = params.get("max_tokens", 4096)
                temperature = params.get("temperature", 0.7)

                # Process with LLM
                result = await self._llm_client.chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                # Store result (could be used for async retrieval)
                logger.info(
                    f"Completed request {request.request_id}: "
                    f"{len(result.get('content', ''))} chars"
                )

        except TimeoutError:
            logger.error(f"Request {request.request_id} timed out")
            raise
        except Exception as e:
            logger.error(f"Error processing request {request.request_id}: {e}")
            raise

#!/usr/bin/env python3
"""
Queue worker process for background LLM request processing.

Usage:
    python scripts/worker.py
    python scripts/worker.py --workers 4
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.redis.client import RedisClient
from app.services.llm.client import VLLMClient
from app.services.queue.consumer import LLMQueueConsumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class WorkerManager:
    """Manages multiple worker instances."""

    def __init__(self, num_workers: int = 1):
        self.num_workers = num_workers
        self.consumers: list[LLMQueueConsumer] = []
        self.tasks: list[asyncio.Task] = []
        self._shutdown = False

    async def start(self) -> None:
        """Start all workers."""
        # Initialize Redis
        redis = await RedisClient.get_instance()

        # Initialize LLM client
        llm_client = VLLMClient()

        logger.info(f"Starting {self.num_workers} worker(s)...")

        # Create consumers
        for i in range(self.num_workers):
            consumer = LLMQueueConsumer(
                redis=redis,
                llm_client=llm_client,
                consumer_name=f"worker-{i}",
            )
            self.consumers.append(consumer)

        # Start tasks
        for consumer in self.consumers:
            task = asyncio.create_task(consumer.start())
            self.tasks.append(task)

        logger.info("All workers started")

        # Wait for shutdown
        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            logger.info("Workers cancelled")

    async def stop(self) -> None:
        """Stop all workers."""
        logger.info("Stopping workers...")
        self._shutdown = True

        # Stop all consumers
        for consumer in self.consumers:
            consumer.stop()

        # Cancel all tasks
        for task in self.tasks:
            task.cancel()

        # Wait for tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        # Disconnect Redis
        redis = await RedisClient.get_instance()
        await redis.disconnect()

        logger.info("All workers stopped")


async def main(num_workers: int) -> None:
    """Main entry point."""
    manager = WorkerManager(num_workers)

    # Setup signal handlers
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(manager.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await manager.start()
    except Exception as e:
        logger.error(f"Worker error: {e}")
        await manager.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM Queue Worker")
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker instances (default: 1)",
    )

    args = parser.parse_args()

    asyncio.run(main(args.workers))

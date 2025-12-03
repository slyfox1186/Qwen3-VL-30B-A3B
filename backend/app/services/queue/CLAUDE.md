# Last Updated: 2025-12-03

## Purpose
Redis Streams-based queue for background LLM request processing with producer/consumer pattern.

## Key Files
- `producer.py` - LLMQueueProducer enqueues chat requests to Redis Stream
- `consumer.py` - LLMQueueConsumer processes requests from stream, handles retries, calls vLLM

## Dependencies/Relations
Used by `scripts/worker.py` (consumer), optional for `api/v1/chat.py` (producer). Depends on `redis/queue`.

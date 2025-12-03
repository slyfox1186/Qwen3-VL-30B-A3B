# Last Updated: 2025-12-03

## Purpose
Standalone scripts for queue workers and Redis server management.

## Key Files
- `worker.py` - Queue worker process manager (multi-worker support), consumes LLM requests from Redis Stream
- `redis_server.py` - Redis server launcher/manager for development

## Dependencies/Relations
Uses `app/services/queue/consumer`, `redis/client`, `services/llm/client`. Runs independently from main API.

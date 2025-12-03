# Last Updated: 2025-12-03

## Purpose
Business logic services for LLM, session management, image processing, queue workers, and web access.

## Key Files
- `llm/` - vLLM client, SSE streaming with <think> tag parsing, message builder
- `session/` - SessionManager, ChatHistoryService for Redis-backed persistence
- `image/` - Image validation, conversion to data URLs
- `queue/` - Producer/consumer for background LLM processing
- `web_access.py` - SerpAPI integration for image search

## Dependencies/Relations
Used by `api/v1/`. Depends on `redis/`, `models/domain/`. Core business logic layer.

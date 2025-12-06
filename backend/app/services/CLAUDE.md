# Last Updated: 2025-12-06

## Purpose
Business logic services for LLM, session management, queue workers, and web access.

## Key Files
- `llm/` - vLLM client, SSE streaming with <think> tag parsing, message builder
- `session/` - SessionManager, ChatHistoryService for Redis-backed persistence
- `queue/` - Producer/consumer for background LLM processing
- `web_access.py` - SerpAPI integration for web search (LLM can find images via search)

## Dependencies/Relations
Used by `api/v1/`. Depends on `redis/`, `models/domain/`. Core business logic layer.

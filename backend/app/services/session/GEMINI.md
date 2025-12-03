# Last Updated: 2025-12-03

## Purpose
Redis-backed session lifecycle and chat history management with TTL, pagination, and automatic trimming.

## Key Files
- `manager.py` - SessionManager handles session CRUD, TTL refresh on access, message count tracking
- `history.py` - ChatHistoryService appends messages to Redis lists, auto-trims to max_messages, paginated retrieval

## Dependencies/Relations
Used by `api/v1/chat.py`, `api/v1/sessions.py`. Depends on `redis/client`, `models/domain/`.

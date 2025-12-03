# Last Updated: 2025-12-03

## Purpose
v1 REST endpoints for chat, sessions, and health checks.

## Key Files
- `chat.py` - POST `/chat` (SSE streaming), `/chat/sync` (non-streaming), tool support, image handling
- `sessions.py` - CRUD for sessions: create, get, delete, clear history, paginated history
- `health.py` - `/health` (basic), `/health/ready` (Redis + vLLM dependency checks)

## Dependencies/Relations
Uses `services/`, `models/schemas`, `dependencies.py`. Registered in `api/router.py`.

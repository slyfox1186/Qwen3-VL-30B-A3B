# Last Updated: 2025-12-03

## Purpose
Core FastAPI application package with lifespan management, routing, configuration, and dependency injection.

## Key Files
- `main.py` - App factory with CORS, middleware, Redis lifespan, exception handlers
- `config.py` - Pydantic Settings (vLLM, Redis, CORS, rate limits, session TTL)
- `dependencies.py` - FastAPI dependency injection (Redis, LLM client, session services)

## Dependencies/Relations
Imports `api/`, `middleware/`, `models/`, `services/`, `redis/`. Instantiated by `backend/run.py`.

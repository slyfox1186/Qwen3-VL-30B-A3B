# Last Updated: 2025-12-03

## Purpose
API routing layer aggregating versioned endpoints (v1).

## Key Files
- `router.py` - Main API router combining health, sessions, chat endpoints with `/api` prefix

## Dependencies/Relations
Imports `v1/` endpoints. Included by `app/main.py` via `app.include_router(api_router)`.

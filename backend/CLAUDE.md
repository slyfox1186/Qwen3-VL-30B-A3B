# Last Updated: 2025-12-03

## Purpose
Backend root: FastAPI server for Qwen3-VL chat with vLLM integration, Redis session management, and SSE streaming.

## Key Files
- `run.py` - Uvicorn server launcher with CLI args (host/port/reload/workers)
- `requirements.txt` - Python dependencies

## Dependencies/Relations
Contains `app/` (core application), `scripts/` (workers, utilities). Used by frontend via REST API.

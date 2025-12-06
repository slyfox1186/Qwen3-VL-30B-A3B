# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Qwen3-VL Chat Application - A vision-language model chat interface using Qwen3-VL-30B-A3B with a FastAPI backend and Next.js frontend.

## Python Environment

**CRITICAL**: Always activate the `qwen` conda environment before running any Python commands:

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qwen
```

All backend Python commands (run.py, run_linter.py, pip, etc.) require this environment.

## Commands

### Run Full Stack (requires user permission)
```bash
python run.py                    # Start frontend + backend + vLLM
python run.py --prod             # Production mode with optimizations
python run.py --no-vllm          # Skip vLLM (if already running)
python run.py --backend-only     # Backend only
python run.py --frontend-only    # Frontend only
```

### Linting (run after all edits)
```bash
python3 run_linter.py            # Runs TypeScript, ESLint, then Ruff sequentially
```

### Frontend (from /frontend)
```bash
npm install                      # Install dependencies
npm run dev                      # Development server (localhost:3000)
npm run build                    # Production build
npm run lint                     # ESLint only
```

### Backend (from /backend)
```bash
pip install -r requirements.txt  # Install dependencies
ruff check .                     # Python linting
ruff check . --fix               # Auto-fix Python issues
```

### Queue Worker
```bash
python backend/scripts/worker.py           # Single worker
python backend/scripts/worker.py --workers 4  # Multiple workers
```

## Architecture

### Backend (FastAPI + Redis)

- **Entry**: `backend/app/main.py` - FastAPI app factory with lifespan management
- **Config**: `backend/app/config.py` - Pydantic Settings from environment variables
- **API Routes**: `backend/app/api/v1/` - Versioned endpoints (chat, sessions, health)

**Data Flow**:
1. Frontend sends POST to `/api/v1/chat` with session ID header
2. `ChatHistoryService` retrieves conversation context from Redis
3. `MessageBuilder` constructs multimodal messages for vLLM
4. `VLLMClient` streams completion via OpenAI-compatible API
5. `SSEStreamHandler` parses `<think>` tags and emits structured SSE events
6. Response saved to Redis history

**Key Services**:
- `services/llm/client.py` - vLLM OpenAI-compatible client
- `services/llm/streaming.py` - SSE streaming with thinking tag extraction
- `services/session/` - Redis-backed session and history management
- `services/image/` - Image validation and base64 conversion
- `redis/` - Connection pool, rate limiting, queue primitives

### Frontend (Next.js 16 + React 19)

- **Entry**: `frontend/src/app/page.tsx` - Main chat interface
- **State**: Zustand stores in `frontend/src/stores/`
  - `chat-store.ts` - Messages, streaming state, thinking/content accumulators
  - `session-store.ts` - Session persistence
- **API Hook**: `frontend/src/hooks/use-chat.ts` - SSE handling, message sending

**SSE Event Types**: `thinking_delta`, `content_delta`, `images`, `error`, `done`

### Communication

- Frontend (3000) -> Backend (8080) -> vLLM (8000)
- Backend uses Redis for session storage and optional queue-based processing
- Images sent as base64 data URLs in multimodal message format

## Environment Variables

Key settings (see `backend/app/config.py`):
- `VLLM_BASE_URL` - vLLM server endpoint (default: http://localhost:8000/v1)
- `VLLM_MODEL` - Model name for API calls
- `REDIS_URL` - Redis connection string
- `BACKEND_HOST/PORT` - Backend binding (default: 0.0.0.0:8080)
- `CORS_ORIGINS` - Allowed frontend origins

## Linting Configuration

- **TypeScript**: `frontend/tsconfig.json` with strict mode
- **ESLint**: `frontend/eslint.config.mjs` with Next.js config
- **Ruff**: `backend/ruff.toml` - Python 3.11, line-length 100, rules E/F/I/N/W/UP

## Rules

- **CSS**: You MUST create a dedicated CSS file for EVERY TSX script instead of using inline CSS.

# Qwen3-VL Chat Application

A full-stack vision-language model chat interface using Qwen3-VL-30B-A3B with a FastAPI backend and Next.js frontend.

## Features

- **Vision-Language Model**: Chat with images using Qwen3-VL-30B-A3B via vLLM
- **Real-time Streaming**: SSE-based response streaming with thinking tag extraction
- **Session Management**: Redis-backed conversation history and session persistence
- **Modern UI**: Next.js 16 + React 19 with Tailwind CSS and Radix UI components
- **Image Upload**: Drag-and-drop or click-to-upload image support
- **Thinking Display**: Collapsible thinking process visualization

## Tech Stack

### Backend
- **FastAPI** - High-performance async web framework
- **vLLM** - OpenAI-compatible inference server
- **Redis** - Session storage and rate limiting
- **Pydantic** - Data validation and settings management
- **SSE-Starlette** - Server-Sent Events streaming

### Frontend
- **Next.js 16** - React framework with App Router
- **React 19** - UI library with React Compiler
- **Zustand** - Lightweight state management
- **Tailwind CSS 4** - Utility-first styling
- **Radix UI** - Accessible component primitives
- **Framer Motion** - Animations

## Prerequisites

- Python 3.11+
- Node.js 20+
- Redis server
- vLLM server with Qwen3-VL-30B-A3B model loaded

## Installation

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # Configure environment variables
```

### Frontend

```bash
cd frontend
npm install
```

## Configuration

Create a `.env` file in the `backend/` directory:

```env
# vLLM Configuration
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_MODEL=Qwen/Qwen3-VL-30B-A3B

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Backend Server
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8080

# CORS
CORS_ORIGINS=["http://localhost:3000"]
```

## Usage

### Run Full Stack

```bash
python run.py                    # Start frontend + backend + vLLM
python run.py --prod             # Production mode with optimizations
python run.py --no-vllm          # Skip vLLM (if already running)
python run.py --backend-only     # Backend only
python run.py --frontend-only    # Frontend only
```

### Run Components Separately

**Backend:**
```bash
cd backend
python run.py
```

**Frontend:**
```bash
cd frontend
npm run dev      # Development
npm run build    # Production build
npm start        # Production server
```

**Queue Worker (optional):**
```bash
python backend/scripts/worker.py           # Single worker
python backend/scripts/worker.py --workers 4  # Multiple workers
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   Backend   │────▶│    vLLM     │
│  (Next.js)  │ SSE │  (FastAPI)  │     │  (OpenAI)   │
│  port:3000  │◀────│  port:8080  │◀────│  port:8000  │
└─────────────┘     └──────┬──────┘     └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │    Redis    │
                   │  (Sessions) │
                   └─────────────┘
```

### Data Flow

1. Frontend sends POST to `/api/v1/chat` with session ID header
2. `ChatHistoryService` retrieves conversation context from Redis
3. `MessageBuilder` constructs multimodal messages for vLLM
4. `VLLMClient` streams completion via OpenAI-compatible API
5. `SSEStreamHandler` parses `<think>` tags and emits structured SSE events
6. Response saved to Redis history

### SSE Event Types

- `thinking_delta` - Incremental thinking content
- `content_delta` - Incremental response content
- `images` - Image references
- `error` - Error messages
- `done` - Stream completion

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API endpoints (chat, sessions, health)
│   │   ├── middleware/      # Error handling, rate limiting
│   │   ├── models/          # Pydantic schemas and domain models
│   │   ├── redis/           # Redis client and utilities
│   │   ├── services/        # Business logic
│   │   │   ├── llm/         # vLLM client and streaming
│   │   │   ├── session/     # Session and history management
│   │   │   └── image/       # Image processing
│   │   ├── config.py        # Settings from environment
│   │   └── main.py          # FastAPI app factory
│   ├── scripts/             # Worker scripts
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js App Router pages
│   │   ├── components/      # React components
│   │   │   ├── chat/        # Chat UI components
│   │   │   └── ui/          # Radix UI primitives
│   │   ├── hooks/           # Custom React hooks
│   │   ├── stores/          # Zustand state stores
│   │   ├── styles/          # CSS files
│   │   └── types/           # TypeScript types
│   └── package.json
├── run.py                   # Full stack launcher
└── run_linter.py            # Linting script
```

## Development

### Linting

```bash
python3 run_linter.py  # Runs TypeScript, ESLint, then Ruff
```

**Individual linters:**
```bash
# Frontend
cd frontend && npm run lint

# Backend
cd backend && ruff check .
cd backend && ruff check . --fix  # Auto-fix
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat` | Send message and stream response |
| GET | `/api/v1/sessions` | List all sessions |
| GET | `/api/v1/sessions/{id}` | Get session details |
| DELETE | `/api/v1/sessions/{id}` | Delete session |
| GET | `/api/v1/health` | Health check |

## License

MIT

# Last Updated: 2025-12-06

## Purpose
Backend root: FastAPI server for Qwen3-VL chat with vLLM integration, Redis session management, and SSE streaming.

## Python Environment
**CRITICAL**: Always activate the `qwen` conda environment before running any Python commands:
```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qwen
```

## Key Files
- `run.py` - Uvicorn server launcher with CLI args (host/port/reload/workers)
- `requirements.txt` - Python dependencies

## Dependencies/Relations
Contains `app/` (core application), `scripts/` (workers, utilities). Used by frontend via REST API.

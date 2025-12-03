#!/usr/bin/env python3
"""
Application runner script.

Usage:
    python run.py
    python run.py --reload
    python run.py --host 0.0.0.0 --port 8080
"""

import argparse

import uvicorn

from app.config import get_settings


def main():
    """Run the FastAPI application."""
    parser = argparse.ArgumentParser(description="VLM Chat API Server")
    parser.add_argument(
        "--host",
        default=None,
        help="Host to bind to (default: from settings)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind to (default: from settings)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)",
    )

    args = parser.parse_args()
    settings = get_settings()

    host = args.host or settings.host
    port = args.port or settings.port

    print(f"Starting {settings.app_name} on {host}:{port}")
    print(f"Debug mode: {settings.debug}")
    print(f"vLLM URL: {settings.vllm_base_url}")
    print(f"Redis URL: {settings.redis_url}")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()

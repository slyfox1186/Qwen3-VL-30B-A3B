"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.middleware.error_handler import setup_exception_handlers
from app.middleware.observability import get_logger, setup_observability
from app.middleware.request_id import RequestIDMiddleware
from app.redis.client import RedisClient

settings = get_settings()

# Get structured logger (configured in setup_observability)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info(f"Starting {settings.app_name}...")

    # Initialize Redis
    redis_client = await RedisClient.get_instance()
    app.state.redis = redis_client
    logger.info("Redis initialized")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await redis_client.disconnect()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Vision-Language Model Chat API for Qwen3-VL-30B-A3B",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    )

    # Request ID middleware (must come before observability for request_id context)
    app.add_middleware(RequestIDMiddleware)

    # Observability (structured logging, metrics, error tracking)
    setup_observability(app)

    # Exception handlers
    setup_exception_handlers(app)

    # Routes
    app.include_router(api_router, prefix="/api")

    return app


app = create_app()

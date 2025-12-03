"""Main API router aggregating all version routers."""

from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.health import router as health_router
from app.api.v1.sessions import router as sessions_router

api_router = APIRouter()

# v1 endpoints
api_router.include_router(health_router, prefix="/v1", tags=["Health"])
api_router.include_router(sessions_router, prefix="/v1", tags=["Sessions"])
api_router.include_router(chat_router, prefix="/v1", tags=["Chat"])

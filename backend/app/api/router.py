"""Main API router aggregating all version routers."""

from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.functions import router as functions_router
from app.api.v1.health import router as health_router
from app.api.v1.images import router as images_router
from app.api.v1.models import router as models_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.ws import router as ws_router

api_router = APIRouter()

# v1 endpoints
api_router.include_router(health_router, prefix="/v1", tags=["Health"])
api_router.include_router(sessions_router, prefix="/v1", tags=["Sessions"])
api_router.include_router(chat_router, prefix="/v1", tags=["Chat"])
api_router.include_router(images_router, prefix="/v1", tags=["Images"])
api_router.include_router(ws_router, prefix="/v1", tags=["WebSocket"])
api_router.include_router(functions_router, prefix="/v1", tags=["Functions"])
api_router.include_router(models_router, prefix="/v1", tags=["Models"])

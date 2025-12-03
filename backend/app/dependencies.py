"""Dependency injection factories."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from app.config import get_settings
from app.redis.client import RedisClient
from app.services.llm.client import VLLMClient
from app.services.session.history import ChatHistoryService
from app.services.session.manager import SessionManager


async def get_redis_client(request: Request) -> RedisClient:
    """Get Redis client from app state."""
    return request.app.state.redis


async def get_session_manager(
    redis: Annotated[RedisClient, Depends(get_redis_client)]
) -> SessionManager:
    """Get session manager instance."""
    settings = get_settings()
    return SessionManager(redis, settings.session_ttl_seconds)


async def get_history_service(
    redis: Annotated[RedisClient, Depends(get_redis_client)]
) -> ChatHistoryService:
    """Get chat history service instance."""
    settings = get_settings()
    return ChatHistoryService(redis, settings.max_history_messages)


async def get_llm_client() -> VLLMClient:
    """Get vLLM client instance."""
    settings = get_settings()
    return VLLMClient(
        base_url=settings.vllm_base_url,
        api_key=settings.vllm_api_key,
        model=settings.vllm_model,
        timeout=settings.vllm_timeout,
    )


async def get_session_id(
    x_session_id: Annotated[str | None, Header()] = None
) -> str:
    """Extract and validate session ID from header."""
    if not x_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "X-Session-ID header is required",
                }
            },
        )
    return x_session_id


async def validate_session(
    session_id: Annotated[str, Depends(get_session_id)],
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
) -> str:
    """Validate session exists and return session ID."""
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": f"Session {session_id} not found or expired",
                }
            },
        )
    return session_id

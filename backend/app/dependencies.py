"""Dependency injection factories."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, WebSocket, status

from app.config import get_settings
from app.redis.client import RedisClient
from app.services.llm.client import VLLMClient
from app.services.llm.qwen_client import QwenAgentClient
from app.services.schema.registry import SchemaRegistry, get_schema_registry
from app.services.schema.validator import SchemaValidator
from app.services.session.history import ChatHistoryService
from app.services.session.manager import SessionManager

# ============================================================================
# HTTP Request Dependencies
# ============================================================================


async def get_redis_client(request: Request) -> RedisClient:
    """Get Redis client from app state (HTTP endpoints)."""
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


# ============================================================================
# WebSocket Dependencies
# ============================================================================


async def get_redis_client_ws(websocket: WebSocket) -> RedisClient:
    """Get Redis client from app state (WebSocket endpoints)."""
    return websocket.app.state.redis


async def get_session_manager_ws(
    redis: Annotated[RedisClient, Depends(get_redis_client_ws)]
) -> SessionManager:
    """Get session manager instance for WebSocket."""
    settings = get_settings()
    return SessionManager(redis, settings.session_ttl_seconds)


async def get_history_service_ws(
    redis: Annotated[RedisClient, Depends(get_redis_client_ws)]
) -> ChatHistoryService:
    """Get chat history service instance for WebSocket."""
    settings = get_settings()
    return ChatHistoryService(redis, settings.max_history_messages)


async def get_llm_client() -> VLLMClient | QwenAgentClient:
    """Get LLM client instance (QwenAgentClient if enabled, else VLLMClient)."""
    settings = get_settings()

    if settings.qwen_agent_enabled:
        return QwenAgentClient(
            base_url=settings.vllm_base_url,
            api_key=settings.vllm_api_key,
            model=settings.vllm_model,
            max_context=settings.vllm_max_model_len,
            timeout=settings.vllm_timeout,
        )

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


def get_schema_registry_dep() -> SchemaRegistry:
    """Get schema registry instance."""
    return get_schema_registry()


def get_schema_validator() -> SchemaValidator:
    """Get schema validator instance."""
    return SchemaValidator()

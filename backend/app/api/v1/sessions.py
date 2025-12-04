"""Session management endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import get_settings
from app.dependencies import (
    get_history_service,
    get_llm_client,
    get_session_manager,
)
from app.models.schemas.session import (
    HistoryMessage,
    SessionCreate,
    SessionHistory,
    SessionResponse,
    SessionUpdate,
    TitleGenerateResponse,
    TruncateHistoryRequest,
    TruncateHistoryResponse,
)
from app.services.llm.client import VLLMClient
from app.services.session.history import ChatHistoryService
from app.services.session.manager import SessionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions")


def _clean_title(raw_title: str) -> str:
    """Clean LLM-generated title by removing quotes and prefixes."""
    title = raw_title.strip()

    # Remove surrounding quotes
    if (title.startswith('"') and title.endswith('"')) or (
        title.startswith("'") and title.endswith("'")
    ):
        title = title[1:-1].strip()

    # Remove common prefixes
    prefixes = ["Title:", "title:", "TITLE:"]
    for prefix in prefixes:
        if title.startswith(prefix):
            title = title[len(prefix) :].strip()
            break

    # Limit to 50 characters
    if len(title) > 50:
        # Try to break at word boundary
        truncated = title[:50]
        last_space = truncated.rfind(" ")
        if last_space > 30:
            title = truncated[:last_space] + "..."
        else:
            title = truncated + "..."

    return title


def _truncate_title(content: str) -> str:
    """Generate fallback title using truncation (mirrors frontend logic)."""
    # Remove image attachment prefix if present
    clean = content.replace("[Image attached]\n", "").replace("[Image attached]", "")
    normalized = " ".join(clean.split()).strip()

    if not normalized:
        return "New conversation"

    max_length = 40
    if len(normalized) <= max_length:
        return normalized

    truncated = normalized[:max_length]
    last_space = truncated.rfind(" ")

    if last_space > max_length * 0.6:
        return truncated[:last_space] + "..."

    return truncated + "..."


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: SessionCreate,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
):
    """
    Create a new chat session.

    Returns the session details including the session ID.
    """
    session = await session_manager.create_session(
        user_id=request.user_id,
        metadata=request.metadata,
    )

    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        created_at=session.created_at_datetime,
        updated_at=session.updated_at_datetime,
        message_count=session.message_count,
        metadata=session.metadata,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
):
    """
    Get session details by ID.
    """
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

    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        created_at=session.created_at_datetime,
        updated_at=session.updated_at_datetime,
        message_count=session.message_count,
        metadata=session.metadata,
    )


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session_metadata(
    session_id: str,
    request: SessionUpdate,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
):
    """
    Update session metadata (partial update).

    Use this to update session title or other metadata fields.
    """
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

    # Merge metadata if provided
    if request.metadata is not None:
        if session.metadata is None:
            session.metadata = {}
        session.metadata.update(request.metadata)

    await session_manager.update_session(session)

    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        created_at=session.created_at_datetime,
        updated_at=session.updated_at_datetime,
        message_count=session.message_count,
        metadata=session.metadata,
    )


@router.get("/{session_id}/history", response_model=SessionHistory)
async def get_session_history(
    session_id: str,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
    history_service: Annotated[ChatHistoryService, Depends(get_history_service)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Get chat history for a session.

    Supports pagination with limit and offset.
    """
    # Validate session exists
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

    # Get history
    messages = await history_service.get_history(session_id, limit=limit, offset=offset)
    total = await history_service.get_history_count(session_id)

    # Convert to response format
    history_messages = [
        HistoryMessage(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            search_results=msg.search_results,
            search_query=msg.search_query,
            created_at=msg.created_at_datetime,
        )
        for msg in messages
    ]

    return SessionHistory(
        session_id=session_id,
        messages=history_messages,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
):
    """
    Delete a session and its history.
    """
    deleted = await session_manager.delete_session(session_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": f"Session {session_id} not found",
                }
            },
        )


@router.post("/{session_id}/clear-history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_session_history(
    session_id: str,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
    history_service: Annotated[ChatHistoryService, Depends(get_history_service)],
):
    """
    Clear chat history while keeping the session.
    """
    # Validate session exists
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

    await history_service.clear_history(session_id)

    # Reset message count
    session.message_count = 0
    await session_manager.update_session(session)


@router.post("/{session_id}/history/truncate", response_model=TruncateHistoryResponse)
async def truncate_session_history(
    session_id: str,
    request: TruncateHistoryRequest,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
    history_service: Annotated[ChatHistoryService, Depends(get_history_service)],
):
    """
    Truncate history at the specified message.

    Removes the specified message and all messages after it.
    Used for message editing flow.
    """
    settings = get_settings()

    # Validate session exists
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

    # Truncate history
    remaining = await history_service.truncate_at_message(
        session_id,
        request.message_id,
        settings.session_ttl_seconds,
    )

    if remaining is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "MESSAGE_NOT_FOUND",
                    "message": f"Message {request.message_id} not found in history",
                }
            },
        )

    # Update session message count
    session.message_count = remaining
    await session_manager.update_session(session)

    return TruncateHistoryResponse(success=True, remaining_count=remaining)


@router.post("/{session_id}/generate-title", response_model=TitleGenerateResponse)
async def generate_session_title(
    session_id: str,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
    history_service: Annotated[ChatHistoryService, Depends(get_history_service)],
    llm_client: Annotated[VLLMClient, Depends(get_llm_client)],
):
    """
    Generate a descriptive title for the session using LLM.

    Uses the first user message to generate a concise title.
    Falls back to truncation if LLM is unavailable.
    """
    # Validate session exists
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

    # Get first messages from history
    messages = await history_service.get_history(session_id, limit=2)
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "NO_MESSAGES",
                    "message": "Session has no messages to generate title from",
                }
            },
        )

    # Find first user message
    first_user_msg = next((m for m in messages if m.role == "user"), None)
    if not first_user_msg or not first_user_msg.content:
        title = "New conversation"
        if session.metadata is None:
            session.metadata = {}
        session.metadata["title"] = title
        await session_manager.update_session(session)
        return TitleGenerateResponse(title=title, generated=False)

    # Prepare LLM prompt (truncate long messages for efficiency)
    content_for_title = first_user_msg.content[:500]
    llm_messages = [
        {
            "role": "system",
            "content": """You are Gemma a helpful AI assistant. Your ONLY task is to generate a 6-word max sidebar title from the user's query.
Return ONLY the title and nothing else.""",
        },
        {"role": "user", "content": content_for_title},
    ]

    # Call LLM for title generation
    try:
        response = await llm_client.chat_completion(
            messages=llm_messages,
            max_tokens=30,
            temperature=0.3,
        )
        raw_title = response.get("content", "").strip()
        title = _clean_title(raw_title) if raw_title else None
        generated = bool(title)
    except Exception as e:
        logger.warning(f"LLM title generation failed for session {session_id}: {e}")
        title = None
        generated = False

    # Fallback to truncation if LLM failed or returned empty
    if not title:
        title = _truncate_title(first_user_msg.content)
        generated = False

    # Update session metadata
    if session.metadata is None:
        session.metadata = {}
    session.metadata["title"] = title
    await session_manager.update_session(session)

    return TitleGenerateResponse(title=title, generated=generated)

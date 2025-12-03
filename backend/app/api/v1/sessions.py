"""Session management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import (
    get_history_service,
    get_session_manager,
)
from app.models.schemas.session import (
    HistoryMessage,
    SessionCreate,
    SessionHistory,
    SessionResponse,
)
from app.services.session.history import ChatHistoryService
from app.services.session.manager import SessionManager

router = APIRouter(prefix="/sessions")


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
            thinking=msg.thinking,
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

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
    SearchMatch,
    SearchPagination,
    SearchRequest,
    SearchResponse,
    SemanticSearchMatch,
    SemanticSearchRequest,
    SemanticSearchResponse,
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
from app.services.session.search import MessageType, SearchFilter, SearchService

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
    normalized = " ".join(content.split()).strip()

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
            "content": "Generate a 6-word max title. Do not think this time and instead return your response IMMEDIATELY.",
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
        raw_title = (response.get("content") or "").strip()
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


@router.post("/search", response_model=SearchResponse)
async def search_messages(
    request: SearchRequest,
    history_service: Annotated[ChatHistoryService, Depends(get_history_service)],
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
):
    """
    Search across conversation history with filters.

    Supports full-text search, date range filtering, and content type filtering.
    Returns highlighted snippets and relevance scores.
    """
    search_service = SearchService()

    # Build search filter from request
    message_type = MessageType.ALL
    if request.message_type:
        try:
            message_type = MessageType(request.message_type.lower())
        except ValueError:
            pass

    filter_ = SearchFilter(
        query=request.query,
        message_type=message_type,
        date_from=request.date_from,
        date_to=request.date_to,
        has_images=request.has_images,
        has_code=request.has_code,
        session_id=request.session_id,
    )

    # Get all messages to search
    # If session_id specified, only get from that session
    # Otherwise, get from all sessions (for now, we'll need a better approach for scale)
    all_messages = []

    if request.session_id:
        # Search within specific session
        session = await session_manager.get_session(request.session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "SESSION_NOT_FOUND",
                        "message": f"Session {request.session_id} not found",
                    }
                },
            )
        messages = await history_service.get_history(request.session_id, limit=1000)
        all_messages.extend(messages)
    else:
        # Search across all sessions - get recent sessions
        sessions = await session_manager.list_recent_sessions(limit=50)
        for session in sessions:
            messages = await history_service.get_history(session.id, limit=200)
            all_messages.extend(messages)

    # Perform search
    result = search_service.search_messages(
        messages=all_messages,
        filter_=filter_,
        page=request.page,
        page_size=request.page_size,
    )

    # Convert to response format
    matches = [
        SearchMatch(
            message_id=m.message_id,
            session_id=m.session_id,
            role=m.role,
            content=m.content[:500] if len(m.content) > 500 else m.content,
            thought=m.thought[:200] if m.thought and len(m.thought) > 200 else m.thought,
            created_at=m.created_at,
            highlights=m.match_highlights,
            relevance=round(m.relevance_score, 3),
            has_images=m.has_images,
            has_code=m.has_code,
        )
        for m in result.matches
    ]

    pagination = SearchPagination(
        total=result.total_count,
        page=result.page,
        page_size=result.page_size,
        total_pages=(result.total_count + result.page_size - 1) // result.page_size,
    )

    return SearchResponse(
        matches=matches,
        pagination=pagination,
        query=result.query,
    )


@router.post("/semantic-search", response_model=SemanticSearchResponse)
async def semantic_search_messages(
    request: SemanticSearchRequest,
    history_service: Annotated[ChatHistoryService, Depends(get_history_service)],
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
):
    """
    Semantic search across conversation history using embeddings.

    Uses vector similarity to find conceptually related messages,
    even if they don't contain the exact search terms.

    Requires sentence-transformers to be installed for embedding generation.
    Returns available=false if the service is not configured.
    """
    # Lazy import to avoid startup errors if sentence-transformers not installed
    try:
        from app.services.embeddings import VectorStore, get_embedding_service

        embedding_service = get_embedding_service()

        if not embedding_service.is_available:
            return SemanticSearchResponse(
                matches=[],
                query=request.query,
                total=0,
                available=False,
            )
    except ImportError:
        return SemanticSearchResponse(
            matches=[],
            query=request.query,
            total=0,
            available=False,
        )

    # We need to get the Redis client - use a workaround for now
    # In production, this would be injected properly
    redis_client = await session_manager._redis.health_check()  # Access internal client
    if not redis_client:
        return SemanticSearchResponse(
            matches=[],
            query=request.query,
            total=0,
            available=False,
        )

    # Create vector store with the session manager's redis client
    vector_store = VectorStore(
        redis_client=session_manager._redis,
        embedding_service=embedding_service,
        namespace="messages",
    )

    # Build filter metadata if session_id specified
    filter_metadata = None
    if request.session_id:
        filter_metadata = {"session_id": request.session_id}

    # Perform semantic search
    results = await vector_store.search(
        query=request.query,
        top_k=request.top_k,
        min_score=request.min_score,
        filter_metadata=filter_metadata,
    )

    # Convert to response format
    matches = [
        SemanticSearchMatch(
            message_id=r.id,
            session_id=r.metadata.get("session_id", "unknown"),
            similarity=round(r.score, 4),
            text_preview=r.metadata.get("text", "")[:300],
            metadata={
                k: v for k, v in r.metadata.items()
                if k not in ("text", "session_id")
            } or None,
        )
        for r in results
    ]

    return SemanticSearchResponse(
        matches=matches,
        query=request.query,
        total=len(matches),
        available=True,
    )


@router.post("/index-messages")
async def index_session_messages(
    session_id: str,
    history_service: Annotated[ChatHistoryService, Depends(get_history_service)],
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
):
    """
    Index all messages in a session for semantic search.

    This is a manual trigger - in production, messages would be indexed
    automatically when saved. Call this to backfill existing conversations.
    """
    from app.config import get_settings

    settings = get_settings()

    # Validate session exists
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": f"Session {session_id} not found",
                }
            },
        )

    # Lazy import
    try:
        from app.services.embeddings import VectorStore, get_embedding_service

        embedding_service = get_embedding_service()
        if not embedding_service.is_available:
            return {"indexed": 0, "available": False, "message": "Embedding service not available"}
    except ImportError:
        return {"indexed": 0, "available": False, "message": "sentence-transformers not installed"}

    # Create vector store
    vector_store = VectorStore(
        redis_client=session_manager._redis,
        embedding_service=embedding_service,
        namespace="messages",
    )

    # Get all messages
    messages = await history_service.get_history(session_id, limit=1000)

    if not messages:
        return {"indexed": 0, "available": True, "message": "No messages to index"}

    # Prepare items for batch indexing
    items = [
        (
            msg.id,
            msg.content,
            {
                "session_id": session_id,
                "role": msg.role,
                "created_at": msg.created_at,
            },
        )
        for msg in messages
        if msg.content  # Skip empty messages
    ]

    # Index all messages
    indexed = await vector_store.add_batch(items, ttl_seconds=settings.session_ttl_seconds)

    return {
        "indexed": indexed,
        "total_messages": len(messages),
        "available": True,
        "message": f"Indexed {indexed} messages from session {session_id}",
    }

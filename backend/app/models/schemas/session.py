"""Pydantic schemas for session management."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    """Session creation request."""

    user_id: str | None = Field(None, description="Optional user identifier")
    metadata: dict[str, Any] | None = Field(None, description="Custom metadata")


class SessionUpdate(BaseModel):
    """Session update request (partial update)."""

    metadata: dict[str, Any] | None = Field(None, description="Metadata to merge/update")


class SessionResponse(BaseModel):
    """Session details response."""

    id: str
    user_id: str | None = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    metadata: dict[str, Any] | None = None


class HistoryMessage(BaseModel):
    """Single message in history."""

    id: str
    role: str = Field(..., description="Message role: user or assistant")
    content: str
    search_results: list[dict[str, Any]] | None = Field(
        None, description="Image search results from tool call"
    )
    search_query: str | None = Field(None, description="Search query used for image search")
    created_at: datetime


class SessionHistory(BaseModel):
    """Paginated session history response."""

    session_id: str
    messages: list[HistoryMessage]
    total: int
    limit: int
    offset: int


class TruncateHistoryRequest(BaseModel):
    """Request to truncate history at a specific message."""

    message_id: str = Field(..., description="ID of message to remove (along with all after)")


class TruncateHistoryResponse(BaseModel):
    """Response after truncating history."""

    success: bool
    remaining_count: int


class TitleGenerateResponse(BaseModel):
    """Response from title generation endpoint."""

    title: str = Field(..., description="Generated or fallback title")
    generated: bool = Field(..., description="True if LLM generated, False if fallback")


class SearchRequest(BaseModel):
    """Search request with filters."""

    query: str | None = Field(None, description="Text to search for")
    message_type: str | None = Field(
        None, description="Filter by role: 'user', 'assistant', or None for all"
    )
    date_from: datetime | None = Field(None, description="Start of date range")
    date_to: datetime | None = Field(None, description="End of date range")
    has_images: bool | None = Field(None, description="Filter messages with/without images")
    has_code: bool | None = Field(None, description="Filter messages with/without code blocks")
    session_id: str | None = Field(None, description="Limit search to specific session")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Results per page")


class SearchMatch(BaseModel):
    """A single search result match."""

    message_id: str
    session_id: str
    role: str
    content: str = Field(..., description="Truncated message content")
    thought: str | None = Field(None, description="Truncated thought content")
    created_at: str
    highlights: list[str] = Field(default_factory=list, description="Highlighted snippets")
    relevance: float = Field(..., description="Relevance score 0-1")
    has_images: bool
    has_code: bool


class SearchPagination(BaseModel):
    """Pagination info for search results."""

    total: int
    page: int
    page_size: int
    total_pages: int


class SearchResponse(BaseModel):
    """Search results response."""

    matches: list[SearchMatch]
    pagination: SearchPagination
    query: str | None


class SemanticSearchRequest(BaseModel):
    """Semantic (vector) search request."""

    query: str = Field(..., min_length=1, max_length=1000, description="Query text for semantic search")
    top_k: int = Field(10, ge=1, le=50, description="Maximum number of results")
    min_score: float = Field(0.5, ge=0.0, le=1.0, description="Minimum similarity score (0-1)")
    session_id: str | None = Field(None, description="Limit search to specific session")


class SemanticSearchMatch(BaseModel):
    """A semantic search result."""

    message_id: str
    session_id: str
    similarity: float = Field(..., description="Cosine similarity score (0-1)")
    text_preview: str = Field(..., description="Truncated message text")
    metadata: dict[str, Any] | None = None


class SemanticSearchResponse(BaseModel):
    """Semantic search results."""

    matches: list[SemanticSearchMatch]
    query: str
    total: int
    available: bool = Field(..., description="True if semantic search is available")

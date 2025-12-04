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

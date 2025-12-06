"""Search service for conversation history with filtering and highlighting."""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from app.models.domain.message import Message


class MessageType(str, Enum):
    """Filter by message role."""

    USER = "user"
    ASSISTANT = "assistant"
    ALL = "all"


@dataclass
class SearchFilter:
    """Search filters for conversation search."""

    query: str | None = None
    message_type: MessageType = MessageType.ALL
    date_from: datetime | None = None
    date_to: datetime | None = None
    has_images: bool | None = None
    has_code: bool | None = None
    session_id: str | None = None


@dataclass
class SearchMatch:
    """A search result match with context and highlighting."""

    message_id: str
    session_id: str
    role: str
    content: str
    thought: str | None
    created_at: str
    match_highlights: list[str]
    relevance_score: float
    has_images: bool
    has_code: bool


@dataclass
class SearchResult:
    """Search result with pagination info."""

    matches: list[SearchMatch]
    total_count: int
    page: int
    page_size: int
    query: str | None


class SearchService:
    """
    Service for searching across conversation history.

    Provides full-text search with filtering, highlighting, and relevance scoring.
    """

    # Pattern to detect code blocks in markdown
    CODE_PATTERN = re.compile(r"```[\s\S]*?```|`[^`]+`")

    # Pattern to detect image references
    IMAGE_PATTERN = re.compile(
        r"\[.*?image.*?attached\]|\!\[.*?\]\(.*?\)|<img\s", re.IGNORECASE
    )

    def __init__(self) -> None:
        pass

    def search_messages(
        self,
        messages: list[Message],
        filter_: SearchFilter,
        page: int = 1,
        page_size: int = 20,
    ) -> SearchResult:
        """
        Search messages with filtering and highlighting.

        Args:
            messages: List of messages to search
            filter_: Search filter criteria
            page: Page number (1-indexed)
            page_size: Results per page

        Returns:
            SearchResult with matches and pagination info
        """
        matches: list[SearchMatch] = []

        for msg in messages:
            # Apply filters
            if not self._matches_filters(msg, filter_):
                continue

            # Calculate relevance and get highlights
            relevance, highlights = self._calculate_relevance(
                msg.content, msg.thought, filter_.query
            )

            if filter_.query and relevance == 0:
                continue  # Query specified but no match

            has_images = bool(self.IMAGE_PATTERN.search(msg.content or ""))
            has_code = bool(self.CODE_PATTERN.search(msg.content or ""))

            matches.append(
                SearchMatch(
                    message_id=msg.id,
                    session_id=msg.session_id or "",
                    role=msg.role,
                    content=msg.content or "",
                    thought=msg.thought,
                    created_at=msg.created_at_datetime.isoformat() if msg.created_at else "",
                    match_highlights=highlights,
                    relevance_score=relevance,
                    has_images=has_images,
                    has_code=has_code,
                )
            )

        # Sort by relevance (highest first) then by date (newest first)
        matches.sort(
            key=lambda m: (-m.relevance_score, m.created_at), reverse=False
        )

        # Pagination
        total_count = len(matches)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_matches = matches[start_idx:end_idx]

        return SearchResult(
            matches=paginated_matches,
            total_count=total_count,
            page=page,
            page_size=page_size,
            query=filter_.query,
        )

    def _matches_filters(self, msg: Message, filter_: SearchFilter) -> bool:
        """Check if message matches all filter criteria."""
        # Message type filter
        if filter_.message_type != MessageType.ALL:
            if msg.role != filter_.message_type.value:
                return False

        # Session filter
        if filter_.session_id and msg.session_id != filter_.session_id:
            return False

        # Date range filter (compare datetime objects)
        if msg.created_at:
            msg_datetime = msg.created_at_datetime
            if filter_.date_from and msg_datetime < filter_.date_from:
                return False
            if filter_.date_to and msg_datetime > filter_.date_to:
                return False

        # Has images filter
        if filter_.has_images is not None:
            has_images = bool(self.IMAGE_PATTERN.search(msg.content or ""))
            if filter_.has_images != has_images:
                return False

        # Has code filter
        if filter_.has_code is not None:
            has_code = bool(self.CODE_PATTERN.search(msg.content or ""))
            if filter_.has_code != has_code:
                return False

        return True

    def _calculate_relevance(
        self, content: str | None, thought: str | None, query: str | None
    ) -> tuple[float, list[str]]:
        """
        Calculate relevance score and extract highlighted snippets.

        Returns:
            Tuple of (relevance_score, list of highlighted snippets)
        """
        if not query:
            return 1.0, []  # No query = everything matches with score 1

        content = content or ""
        thought = thought or ""
        full_text = f"{content} {thought}".lower()
        query_lower = query.lower()

        # Check for exact phrase match
        if query_lower in full_text:
            # Count occurrences
            count = full_text.count(query_lower)
            base_score = min(count * 0.25, 1.0)

            # Boost for content match (vs thought match)
            if query_lower in content.lower():
                base_score += 0.3

            highlights = self._extract_highlights(content, query, max_highlights=3)
            return min(base_score + 0.5, 1.0), highlights

        # Check for word-level matches
        query_words = set(query_lower.split())
        text_words = set(full_text.split())
        matching_words = query_words & text_words

        if matching_words:
            score = len(matching_words) / len(query_words)
            highlights = self._extract_highlights(content, query, max_highlights=2)
            return score * 0.7, highlights

        return 0.0, []

    def _extract_highlights(
        self, content: str, query: str, max_highlights: int = 3, context_chars: int = 80
    ) -> list[str]:
        """Extract highlighted snippets with surrounding context."""
        if not content or not query:
            return []

        highlights: list[str] = []
        content_lower = content.lower()
        query_lower = query.lower()

        # Find all occurrences
        start = 0
        while len(highlights) < max_highlights:
            idx = content_lower.find(query_lower, start)
            if idx == -1:
                break

            # Extract context around match
            ctx_start = max(0, idx - context_chars)
            ctx_end = min(len(content), idx + len(query) + context_chars)

            snippet = content[ctx_start:ctx_end]

            # Add ellipsis if truncated
            if ctx_start > 0:
                snippet = "..." + snippet
            if ctx_end < len(content):
                snippet = snippet + "..."

            # Highlight the match with markers
            match_start = idx - ctx_start + (3 if ctx_start > 0 else 0)
            match_end = match_start + len(query)
            highlighted = (
                snippet[:match_start]
                + "**"
                + snippet[match_start:match_end]
                + "**"
                + snippet[match_end:]
            )

            highlights.append(highlighted)
            start = idx + 1

        return highlights

    def search_to_dict(self, result: SearchResult) -> dict[str, Any]:
        """Convert SearchResult to JSON-serializable dict."""
        return {
            "matches": [
                {
                    "message_id": m.message_id,
                    "session_id": m.session_id,
                    "role": m.role,
                    "content": m.content[:500] if len(m.content) > 500 else m.content,
                    "thought": m.thought[:200] if m.thought and len(m.thought) > 200 else m.thought,
                    "created_at": m.created_at,
                    "highlights": m.match_highlights,
                    "relevance": round(m.relevance_score, 3),
                    "has_images": m.has_images,
                    "has_code": m.has_code,
                }
                for m in result.matches
            ],
            "pagination": {
                "total": result.total_count,
                "page": result.page,
                "page_size": result.page_size,
                "total_pages": (result.total_count + result.page_size - 1) // result.page_size,
            },
            "query": result.query,
        }

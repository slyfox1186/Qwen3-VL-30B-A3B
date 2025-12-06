"""Domain models for messages."""

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Message:
    """Chat message domain model."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: str = "user"  # user or assistant
    content: str = ""
    thought: str | None = None
    search_results: list[dict[str, Any]] | None = None
    search_query: str | None = None
    created_at: float = field(default_factory=time.time)
    session_id: str | None = None
    # Thread system fields
    thread_id: str | None = None  # ID of thread this message belongs to
    is_pinned: bool = False  # Whether message is pinned to top
    thread_position: int | None = None  # Position within thread

    @property
    def created_at_datetime(self) -> datetime:
        """Get created_at as datetime."""
        return datetime.fromtimestamp(self.created_at)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "thought": self.thought,
            "search_results": self.search_results,
            "search_query": self.search_query,
            "created_at": self.created_at,
            "session_id": self.session_id,
            "thread_id": self.thread_id,
            "is_pinned": self.is_pinned,
            "thread_position": self.thread_position,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            role=data["role"],
            content=data["content"],
            thought=data.get("thought"),
            search_results=data.get("search_results"),
            search_query=data.get("search_query"),
            created_at=data.get("created_at", time.time()),
            session_id=data.get("session_id"),
            thread_id=data.get("thread_id"),
            is_pinned=data.get("is_pinned", False),
            thread_position=data.get("thread_position"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Message":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def to_api_format(self) -> dict[str, Any]:
        """Convert to API response format."""
        result = {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at_datetime.isoformat(),
        }

        if self.thought:
            result["thought"] = self.thought

        if self.search_results:
            result["search_results"] = self.search_results

        if self.search_query:
            result["search_query"] = self.search_query

        if self.thread_id:
            result["thread_id"] = self.thread_id

        if self.is_pinned:
            result["is_pinned"] = self.is_pinned

        if self.thread_position is not None:
            result["thread_position"] = self.thread_position

        return result

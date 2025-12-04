"""Domain models for messages."""

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ImageAttachment:
    """Image attachment in a message."""

    data_url: str
    media_type: str
    size_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "data_url": self.data_url,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageAttachment":
        """Create from dictionary."""
        return cls(
            data_url=data["data_url"],
            media_type=data["media_type"],
            size_bytes=data.get("size_bytes"),
        )


@dataclass
class Message:
    """Chat message domain model."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: str = "user"  # user or assistant
    content: str = ""
    thought: str | None = None
    images: list[ImageAttachment] = field(default_factory=list)
    search_results: list[dict[str, Any]] | None = None
    search_query: str | None = None
    created_at: float = field(default_factory=time.time)
    session_id: str | None = None

    @property
    def created_at_datetime(self) -> datetime:
        """Get created_at as datetime."""
        return datetime.fromtimestamp(self.created_at)

    @property
    def has_images(self) -> bool:
        """Check if message has images."""
        return len(self.images) > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "thought": self.thought,
            "images": [img.to_dict() for img in self.images],
            "search_results": self.search_results,
            "search_query": self.search_query,
            "created_at": self.created_at,
            "session_id": self.session_id,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """Create from dictionary."""
        images = [
            ImageAttachment.from_dict(img)
            for img in data.get("images", [])
        ]
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            role=data["role"],
            content=data["content"],
            thought=data.get("thought"),
            images=images,
            search_results=data.get("search_results"),
            search_query=data.get("search_query"),
            created_at=data.get("created_at", time.time()),
            session_id=data.get("session_id"),
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

        if self.images:
            result["images"] = [img.data_url for img in self.images]

        if self.search_results:
            result["search_results"] = self.search_results

        if self.search_query:
            result["search_query"] = self.search_query

        return result

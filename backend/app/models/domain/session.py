"""Domain models for sessions."""

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Session:
    """Chat session domain model."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    message_count: int = 0
    metadata: dict[str, Any] | None = None

    @property
    def created_at_datetime(self) -> datetime:
        """Get created_at as datetime."""
        return datetime.fromtimestamp(self.created_at)

    @property
    def updated_at_datetime(self) -> datetime:
        """Get updated_at as datetime."""
        return datetime.fromtimestamp(self.updated_at)

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = time.time()

    def increment_messages(self, count: int = 1) -> None:
        """Increment message count."""
        self.message_count += count
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            user_id=data.get("user_id"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            message_count=data.get("message_count", 0),
            metadata=data.get("metadata"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Session":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def to_api_response(self) -> dict[str, Any]:
        """Convert to API response format."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_at": self.created_at_datetime.isoformat(),
            "updated_at": self.updated_at_datetime.isoformat(),
            "message_count": self.message_count,
            "metadata": self.metadata,
        }
